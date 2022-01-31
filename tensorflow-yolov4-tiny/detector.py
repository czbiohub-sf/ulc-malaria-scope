import os
import cv2
import time
import logging as log
import sys
from argparse import ArgumentParser
from openvino.inference_engine import IECore, IENetwork


def get_parser():
    parser = ArgumentParser()
    # Path to the folder with model and file to process
    parser.add_argument("-m", "--model_path", help="Path to the folder with the model", required=True, type=str)
    parser.add_argument("-i", "--input",
                        help="Path to video file or image. Default 'cam'", default="cam",
                        type=str)
    parser.add_argument("-o", "--output",
                        help="Path to folder to save file", default=None, type=str)

    parser.add_argument("-r", "--resolution", help="Resolution for the image example 640X480",
                        default='640X480', type=str)

    # Selecting a device to make DNN computations
    parser.add_argument("-d", "--device",
                        help="Target device CPU or MYRIAD"
                             "if CPU pass --cpu_extension as well", default="CPU",
                        type=str)
    #
    parser.add_argument("-l", "--cpu_extension",
                        help="Path to the MKLDNN library for the CPU check at"
                             "/deployment_tools/inference_engine/lib", type=str, default=None)

    # Labels for the neural network
    parser.add_argument("--labels", help="Labels mapping file", default=None, type=str)
    # Probability threshold
    parser.add_argument("-pt", "--prob_threshold", help="Probability threshold for detections filtering",
                        default=0.5, type=float)
    return parser


def load_to_IE(model, device):
    # Getting the *.bin file location
    model_bin = model[:-3] + "bin"
    # Loading the Inference Engine API
    ie = IECore()
    # Loading IR files
    net = ie.read_network(model=model, weights=model_bin)
    # Loading the network to the inference engine
    exec_net = ie.load_network(network=net, device_name=device)
    print("IR successfully loaded into Inference Engine.")
    return exec_net


def sync_inference(exec_net, image):
    input_blob = next(iter(exec_net.inputs))
    return exec_net.infer({input_blob: image})


def load_labels(path, encoding="utf-8"):
    """Loads labels from file (with or without index numbers).

    Args:
    path: path to label file.
    encoding: label file encoding.
    Returns:
    Dictionary mapping indices to labels.
    """
    with open(path, "r", encoding=encoding) as f:
        lines = f.readlines()
        if not lines:
            return {}

    if lines[0].split(" ", maxsplit=1)[0].isdigit():
        pairs = [line.split(" ", maxsplit=1) for line in lines]
        return {int(index): label.strip() for index, label in pairs}
    else:
        return {index: line.strip() for index, line in enumerate(lines)}


def main():
    log.basicConfig(format="[ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
    args = get_parser().parse_args()
    log.info("Initializing plugin for {} device".format(args.device))

    # Read IR
    for f in os.listdir(args.model_path):
        if f[-3:] == 'bin':
            weights = os.path.join(args.model_path, f)
        if f[-3:] == 'xml':
            model = os.path.join(args.model_path, f)
    exec_net = load_to_IE(model, args.device)
    # Plugin initialization for specified device and load extensions library if specified

    log.info("Reading IR")
    net = IENetwork(model=model, weights=weights)
    input_blob = next(iter(net.inputs))
    out_blob = next(iter(net.outputs))
    log.info("Loading IR to the plugin")
    # Get labels dict
    if args.labels:
        labels_map = load_labels(args.labels)
    # Read and pre-process input image
    n, c, h, w = net.inputs[input_blob].shape
    del net
    if args.input == 'cam':
        input_stream = 0
    elif len(args.input) < 3:
        input_stream = int(args.input)
    else:
        input_stream = args.input
        assert os.path.isfile(args.input), "Specified input file doesn't exist"

    cap = cv2.VideoCapture(input_stream)
    stream_w, stream_h = (int(x) for x in args.resolution.split('X'))
    cap.set(3, stream_w)
    cap.set(4, stream_h)
    cur_request_id = 0
    next_request_id = 1

    log.info("Starting inference in async mode...")
    log.info("To switch between sync and async modes press Tab button")
    log.info("To stop the demo execution press Esc button")

    render_time = 0
    freq = cv2.getTickFrequency()
    ret, frame = cap.read()
    is_async_mode = False

    # Write to the output file
    # add parameters

    if args.output:
        fps = cap.get(cv2.CAP_PROP_FPS)
        file_name = os.path.join(
            args.output, '{}-{}.avi'.format(time.strftime("%Y%m%d-%H%M%S"), args.device))
        out = cv2.VideoWriter(
            file_name, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'), fps, (640, 480))

    while cap.isOpened():

        t1 = cv2.getTickCount()

        if is_async_mode:
            ret, next_frame = cap.read()
        else:
            ret, frame = cap.read()
        if not ret:
            break

        initial_w = cap.get(3)
        initial_h = cap.get(4)
        # Main sync point:
        # in the truly Async mode we start the NEXT infer request, while waiting for the CURRENT to complete
        # in the regular mode we start the CURRENT request and immediately wait for it's completion
        inf_start = time.time()

        if is_async_mode:
            in_frame = cv2.resize(next_frame, (w, h))
            in_frame = in_frame.transpose((2, 0, 1))  # Change data layout from HWC to CHW
            in_frame = in_frame.reshape((n, c, h, w))
            exec_net.start_async(request_id=next_request_id, inputs={input_blob: in_frame})
        else:
            in_frame = cv2.resize(frame, (w, h))
            in_frame = in_frame.transpose((2, 0, 1))  # Change data layout from HWC to CHW
            in_frame = in_frame.reshape((n, c, h, w))
            exec_net.start_async(request_id=cur_request_id, inputs={input_blob: in_frame})

        if exec_net.requests[cur_request_id].wait(-1) == 0:
            inf_end = time.time()
            det_time = inf_end - inf_start

            # Parse detection results of the current request
            res = exec_net.requests[cur_request_id].outputs
            print(res)
            for obj in res[0][0]:
                print(obj)
                # Draw only objects when probability more than specified threshold
                if obj[2] > args.prob_threshold:
                    xmin = int(obj[3] * initial_w)
                    ymin = int(obj[4] * initial_h)
                    xmax = int(obj[5] * initial_w)
                    ymax = int(obj[6] * initial_h)
                    class_id = int(obj[1])
                    # Draw box and label\class_id
                    color = (min(class_id * 4, 255), min(class_id * 3 + 100, 255), min(class_id * 2, 255))
                    cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), color, 2)
                    det_label = labels_map[class_id] if args.labels else str(class_id)
                    cv2.putText(frame, det_label +' ' + str(round(obj[2] * 100, 1)) + ' %', (xmin, ymin - 7),
                                cv2.FONT_HERSHEY_COMPLEX, 0.6, color, 1)

            t2 = cv2.getTickCount()
            time1 = (t2 - t1) / freq
            frame_rate_calc = 1 / time1

            # Draw performance stats
            inf_time_message = "Inference time: N\A for async mode" if is_async_mode else \
                "Inference time: {:.3f} ms".format(det_time * 1000)
            render_time_message = "OpenCV rendering time: {:.3f} ms".format(render_time * 1000)
            FPS_message = "FPS: {:.2f}".format(frame_rate_calc)
            async_mode_message = "Async mode is on. Processing request {}".format(cur_request_id) if is_async_mode else \
                "Async mode is off. Processing request {}".format(cur_request_id)

            cv2.putText(frame, inf_time_message, (15, 15), cv2.FONT_HERSHEY_COMPLEX, 0.5, (200, 10, 10), 1)
            cv2.putText(frame, render_time_message, (15, 30), cv2.FONT_HERSHEY_COMPLEX, 0.5, (10, 10, 200), 1)
            cv2.putText(frame, FPS_message, (15, 45), cv2.FONT_HERSHEY_COMPLEX, 0.5, (10, 10, 200), 1)
            cv2.putText(frame, async_mode_message, (10, int(initial_h - 20)), cv2.FONT_HERSHEY_COMPLEX, 0.5,
                        (10, 10, 200), 1)
            if args.output:
                out.write(frame)
        #
        render_start = time.time()
        cv2.imshow("Detection Results", frame)
        render_end = time.time()
        render_time = render_end - render_start

        if is_async_mode:
            cur_request_id, next_request_id = next_request_id, cur_request_id
            frame = next_frame

        key = cv2.waitKey(1)
        if key == 27:
            break
        if key == 9:
            is_async_mode = not is_async_mode
            log.info("Switched to {} mode".format("async" if is_async_mode else "sync"))

    cap.release()
    if args.output:
        out.release()

    cv2.destroyAllWindows()
    del exec_net

if __name__ == '__main__':
    sys.exit(main() or 0)
