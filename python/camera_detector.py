import cv2
import numpy as np
import yaml

import multibag as mb
import numpystream as ns

def read_ost_yaml():
    ost_yaml_path = '/home/eljefec/repo/didi-competition/calibration/ost.yaml'
    with open(ost_yaml_path , 'r') as f:
        return yaml.load(f)

def read_ost_array(ost, field):
    ost_cm = ost[field]
    return np.array(ost_cm['data']).reshape(ost_cm['rows'], ost_cm['cols'])

def lidar_point_to_camera_origin(point):
    # Based on https://github.com/udacity/didi-competition/blob/master/mkz-description/mkz.urdf.xacro
    return (point - [1.9304 - 1.5494, 0, 0.9398 - 1.27])

class Undistorter:
    def __init__(self):
        ost = read_ost_yaml()
        self.camera_matrix = read_ost_array(ost, 'camera_matrix')
        self.distortion_coefficients = read_ost_array(ost, 'distortion_coefficients')
        self.projection_matrix = read_ost_array(ost, 'projection_matrix')

    def undistort_image(self, im):
        return cv2.undistort(im, self.camera_matrix, self.distortion_coefficients)

    def project_point(self, lidar_point):
        # See formulas at http://docs.opencv.org/2.4/modules/calib3d/doc/camera_calibration_and_3d_reconstruction.html
        object_point = lidar_point_to_camera_origin(lidar_point)
        z_camera = object_point[0]
        x_camera = -object_point[1]
        y_camera = -object_point[2]
        camera_coord = np.array([x_camera, y_camera, z_camera, 1.0]).transpose()
        image_point = np.dot(self.projection_matrix, camera_coord)
        image_point /= image_point[2]
        return image_point

    def project_points(self, obj_points):
        count = obj_points.shape[0]
        img_points = np.zeros((count, 3))
        for i in range(count):
            img_points[i] = self.project_point(obj_points[i])
        return img_points

def try_undistort(desired_count):
    undist = Undistorter()

    bagdir = '/data/bags/didi-round2/release/car/training/suburu_leading_at_distance'
    bt = mb.find_bag_tracklets(bagdir, '/data/tracklets')
    multi = mb.MultiBagStream(bt, ns.generate_numpystream)
    generator = multi.generate(infinite = False)
    count = 0
    output_count = 0
    for numpydata in generator:
        im = numpydata.image
        frame_idx, obs = numpydata.obs
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        undistorted = undist.undistort_image(im)
        if count % 25 == 0:
            cv2.imwrite('/data/dev/camera/orig_{}.png'.format(count), im)

            # Print center.
            img_point = undist.project_point(obs.position)
            cv2.circle(undistorted, (int(img_point[0]), int(img_point[1])), radius = 5, color = (255, 0, 0), thickness=2)

            # Print bbox corners.
            img_points = undist.project_points(obs.get_bbox().transpose())
            for img_point in img_points:
                cv2.circle(undistorted, (int(img_point[0]), int(img_point[1])), radius = 5, color = (0, 255, 0), thickness=2)

            cv2.imwrite('/data/dev/camera/undist_{}.png'.format(count), undistorted)
            output_count += 1
        count += 1
        if desired_count is not None and output_count == desired_count:
            return

if __name__ == '__main__':
    import os
    path = '/data/dev/camera'
    if not os.path.exists(path):
        os.makedirs('/data/dev/camera')
    try_undistort(None)