import numpy as np

X_TOL = 15

def getFlowRateInPixels(prev_bboxes, curr_bboxes):
    """
    Returns the flow rate in number of pixels based on the previous and current frame bounding boxes
    
    Parameters
    ----------
    prev_bboxes : List[BBox]
        A list of BBox objects from the previous frame
    curr_bboxes : List[BBox] 
        A list of BBox objects from the current frame

    Returns
    -------
    int:
        An integer representing the average bounding box displacements found between the previous and current frame

    """
    # Extract relevant parameters from the BBox class
    prev_xmin = np.asarray([bbox.xmin for bbox in prev_bboxes])
    prev_ymin = np.asarray([bbox.ymin for bbox in prev_bboxes])
    prev_xmax = np.asarray([bbox.xmax for bbox in prev_bboxes])
    curr_xmin = np.asarray([bbox.xmin for bbox in curr_bboxes])
    curr_ymin = np.asarray([bbox.ymin for bbox in curr_bboxes])
    curr_xmax = np.asarray([bbox.xmax for bbox in curr_bboxes])
    
    all_displacements = []

    for i, (c_xmin, c_xmax) in enumerate(zip(curr_xmin, curr_xmax)):
        # If there are multiple bounding boxes in the current frame in the same vertical region
        if np.count_nonzero(np.isclose(curr_xmin, c_xmin, atol=X_TOL)) > 1:
            continue

        # Find the bounding box in the previous frame corresponding to the current box
        index_xmin_in_prev_frame = np.argwhere( np.isclose(prev_xmin, c_xmin, atol=X_TOL) == True)
        index_xmax_in_prev_frame = np.argwhere( np.isclose(prev_xmax, c_xmax, atol=X_TOL) == True)

        # Ensure there is only one bounding box in the previous frame which corresponds to the current 
        if len(index_xmin_in_prev_frame > 0) and len(index_xmax_in_prev_frame > 0):
            if len(index_xmin_in_prev_frame[0]) == 1:
                # Find the y displacement
                c_ymin = curr_ymin[i]
                p_ymin = prev_ymin[index_xmin_in_prev_frame[0][0]]

                if p_ymin < c_ymin:
                    pixel_displacement = c_ymin - p_ymin
                    all_displacements.append(pixel_displacement)
    
    return np.average(all_displacements)

def convertPixelToDistance(pixels):
    # TODO
    return 1