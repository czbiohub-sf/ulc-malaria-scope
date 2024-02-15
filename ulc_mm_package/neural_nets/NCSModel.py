#! /usr/bin/env python3

import time
import threading
import numpy as np
import operator as op
import numpy.typing as npt

from copy import copy
from concurrent.futures import ThreadPoolExecutor

from functools import partial
from collections import namedtuple
from typing import (
    Any,
    List,
    Sequence,
    Optional,
    Union,
    TypeVar,
)

from ulc_mm_package.utilities.lock_utils import lock_timeout


from openvino.preprocess import PrePostProcessor
from openvino.runtime import (
    Core,
    Layout,
    Type,
    InferRequest,
    AsyncInferQueue,
)


T = TypeVar("T", covariant=True)


class GPUError(Exception):
    pass


AsyncInferenceResult = namedtuple("AsyncInferenceResult", ["id", "result"])


class NCSModel:
    """
    Neural Compute Stick 2 Model

    Allows you to run a model (defined by an intel intermediate representation of your
    model, e.g. model.xml & model.bin) on the neural compute stick

    Best docs
    https://docs.openvino.ai/latest/api/ie_python_api/api.html
    https://docs.openvino.ai/latest/openvino_docs_OV_UG_Python_API_exclusives.html
    """

    core = None

    def __init_subclass__(cls, *args, **kwargs):
        if NCSModel.core is None:
            NCSModel.core = Core()
        cls.core = NCSModel.core

    def __init__(
        self,
        model_path: str,
    ):
        """
        params:
            model_path: path to the 'xml' file
        """
        self.connected = False
        self.device_name = "MYRIAD"
        self.model = self._compile_model(model_path)

        self.asyn_result_lock = threading.Lock()

        # used for syn
        self._temp_infer_queue = AsyncInferQueue(self.model)

        # used for asyn
        self.asyn_infer_queue = AsyncInferQueue(self.model)
        self.asyn_infer_queue.set_callback(self._default_callback)
        self._asyn_results: List[AsyncInferenceResult] = []

        self._executor = ThreadPoolExecutor(max_workers=1)

    def _compile_model(
        self,
        model_path: str,
    ):
        if self.connected:
            raise RuntimeError(f"model {self} already compiled")

        # when the first subclass is initialized, core will be given a value
        assert (
            self.core is not None
        ), "initialize a subclass of NCSModel, not NCSModel itself"

        model = self.core.read_model(model_path)

        ppp = PrePostProcessor(model)
        ppp.input().tensor().set_element_type(Type.u8).set_layout(Layout("NHWC"))
        ppp.input().model().set_layout(Layout("NCHW"))
        ppp.output().tensor().set_element_type(Type.f16)
        model = ppp.build()

        err_msg = ""
        connection_attempts = 0
        while connection_attempts < 4:
            # sleep 0, then 1, then 3, then 7
            time.sleep(2**connection_attempts - 1)
            try:
                compiled_model = self.core.compile_model(
                    model,
                    self.device_name,
                )
                self.connected = True
                return compiled_model
            except Exception as e:
                connection_attempts += 1
                if connection_attempts < 4:
                    print(
                        f"Failed to connect NCS: {e}.\nRemaining connection "
                        f"attempts: {4 - connection_attempts}. Retrying..."
                    )
                err_msg = str(e)
        raise GPUError(f"Failed to connect to NCS: {err_msg}")

    def syn(
        self, input_imgs: Union[npt.NDArray, List[npt.NDArray]], sort: bool = False
    ) -> List[npt.NDArray]:
        """'Synchronously' infers images on the NCS

        Under the hood, it is asynchronous, because asynchronous performance matches synchronous
        or bests synchronous performance, even for n = 1.

        This is a "synchronous" function
        in the sense that it blocks. I.e. it blocks until it returns a result, as opposed to
        asynchronous inference which would immediately return.

        params:
            input_imgs: the image/images to be inferred.
            sort: sort the outputs
        """
        res: List[AsyncInferenceResult] = []

        self._temp_infer_queue.set_callback(partial(self._cb, res))

        for i, image in enumerate(self._as_sequence(input_imgs)):
            tensor = self._format_image_to_tensor(image)
            self._temp_infer_queue.start_async({0: tensor}, userdata=i)

        self._temp_infer_queue.wait_all()

        if sort:
            return [r.result for r in sorted(res, key=op.attrgetter("id"))]
        return [r.result for r in res]

    def asyn(
        self,
        input_img: npt.NDArray,
        id: Optional[int] = None,
    ) -> None:
        """Asynchronously submits inference jobs to the NCS

        params:
            input_imgs: the image/images to be inferred.
            ids: the ids that are passed through the asynchronous inference,
                 used for associating the predicted tensor with the input image.

        To get results, call 'get_asyn_results'
        """
        input_tensor = self._format_image_to_tensor(input_img)

        self._executor.submit(
            self.asyn_infer_queue.start_async,
            inputs={0: input_tensor},
            userdata=id,
        )

    def get_asyn_results(
        self, timeout: Optional[float] = 0.01
    ) -> List[AsyncInferenceResult]:
        """
        Maybe return some asyn_results. Will return an empty list if it can not get the lock
        on results within `timeout`. To disable timeout (i.e. just block indefinitely),
        set `timeout` to None
        """
        # openvino sets timeout to indefinite on timeout < 0, not timeout == None
        if timeout is None:
            timeout = -1

        res = []

        with lock_timeout(self.asyn_result_lock, timeout=timeout):
            res = copy(self._asyn_results)
            self._asyn_results = []

        return res

    def work_queue_size(self) -> int:
        return self._executor._work_queue.qsize()

    def _default_callback(self, infer_request: InferRequest, userdata: Any) -> None:
        r = AsyncInferenceResult(
            id=userdata, result=infer_request.output_tensors[0].data.copy()
        )
        with lock_timeout(self.asyn_result_lock):
            self._asyn_results.append(r)

    def _cb(
        self, result_list: List, infer_request: InferRequest, userdata: Any
    ) -> None:
        result_list.append(
            AsyncInferenceResult(
                id=userdata, result=infer_request.output_tensors[0].data.copy()
            )
        )

    def _as_sequence(self, maybe_list: Union[T, List[T]]) -> Sequence[T]:
        if isinstance(maybe_list, Sequence):
            return maybe_list
        return [maybe_list]

    def _format_image_to_tensor(self, img: npt.NDArray) -> npt.NDArray:
        dims = img.shape
        if len(dims) == 2:
            return np.expand_dims(img, (0, 3))
        elif len(dims) == 3 and dims[0] == 1:
            return np.expand_dims(img, 3)
        elif len(dims) == 3 and dims[-1] == 1:
            return np.expand_dims(img, 0)
        elif len(dims) == 4 and dims[0] == dims[-1] == 1:
            return img
        else:
            raise ValueError(
                f"Invalid shape for img; got {dims}, but need\n"
                "\t(h, w), (1, h, w), (h, w, 1), or (1, h, w, 1)"
            )

    def wait_all(self) -> None:
        """wait for all pending InferRequests to finish"""
        # very rough wait for rest of the ThreadPoolExecutor to finish
        while self.work_queue_size() > 0:
            time.sleep(0.01)

        self.asyn_infer_queue.wait_all()
        self._temp_infer_queue.wait_all()

    def reset(self, wait: bool = True) -> List[AsyncInferenceResult]:
        """
        wait for the NCS's AsyncInferQueue to finish, then reset the
        ThreadPoolExecutor. Note that this will not drop the reference to the NCS.

        If wait is True, this will wait until every image in the queue is finished
        and then will return the results. Otherwise, it purges the queues and returns
        whatever images were in self._asyn_results or the asyn_infer_queues. Note that
        in this case, you *will* be dropping jobs. In either case, the NCSModel will
        be reset after this call.
        """
        # this short-cuts waiting for the jobs in the ThreadPoolExecutor if wait=False
        self._executor.shutdown(wait=wait)

        # this waits for the ThreadPoolExecutor (now empty, so it'll be very fast),
        # and then for the AsyncInferQueues
        self.wait_all()

        # this is the official way of restarting a ThreadPoolExecutor
        self._executor = ThreadPoolExecutor(max_workers=1)

        # resets self._asyn_results and returns a list of AsyncInferenceResults
        return self.get_asyn_results()
