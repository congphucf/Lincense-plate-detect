from ultralytics import YOLO
import cv2
import numpy as np
import util
from deep_sort_realtime.deepsort_tracker import DeepSort
from util import get_car, read_license_plate, write_csv


results = {}

mot_tracker = DeepSort()

# load models
coco_model = YOLO('yolov8n.pt')
license_plate_detector = YOLO('license_plate_detector.pt')

# load video
cap = cv2.VideoCapture('./sample.mp4')

vehicles = [2, 3, 5, 7]

# read frames
frame_nmr = -1
ret = True
while ret:
    frame_nmr += 1
    ret, frame = cap.read()
    if ret:
        results[frame_nmr] = {}
        # detect vehicles
        detections = coco_model(frame)[0]
        detections_ = []
        for detection in detections.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = detection
            if int(class_id) in vehicles:
                detections_.append([ [x1, y1, x2-x1, y2 - y1], score, int(class_id) ])

        # track vehicles
        tracks = mot_tracker.update_tracks(detections_, frame=frame)
        track_ids = []
        for track in tracks:
            if not track.is_confirmed() or track.time_since_update > 1:
                continue
            bbox = list(track.to_tlbr())
            track_id = int(track.track_id)
            track_ids.append((bbox[0], bbox[1], bbox[2], bbox[3], track_id))
        

        # detect license plates
        license_plates = license_plate_detector(frame)[0]
        for license_plate in license_plates.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = license_plate

            # assign license plate to car
            xcar1, ycar1, xcar2, ycar2, car_id = get_car(license_plate, track_ids)

            if car_id != -1:

                # crop license plate
                license_plate_crop = frame[int(y1):int(y2), int(x1): int(x2), :]

                # process license plate
                license_plate_crop_gray = cv2.cvtColor(license_plate_crop, cv2.COLOR_BGR2GRAY)
                _, license_plate_crop_thresh = cv2.threshold(license_plate_crop_gray, 64, 255, cv2.THRESH_BINARY_INV)

                # read license plate number
                license_plate_text, license_plate_text_score = read_license_plate(license_plate_crop_thresh)
                print(license_plate_text)
                xcar1, ycar1 = int(xcar1), int(ycar1)
                xcar2, ycar2 = int(xcar2), int(ycar2)
                x1 , x2, y1, y2 = int(x1), int(x2), int(y1), int(y2)

                car_box = cv2.rectangle(frame, (xcar1, ycar1), (xcar2, ycar2), (255, 255, 0), 2)
                license_plate_box = cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 0), 2)

                if license_plate_text is not None:
                    results[frame_nmr][car_id] = {'car': {'bbox': [xcar1, ycar1, xcar2, ycar2]},
                                                    'license_plate': {'bbox': [x1, y1, x2, y2],
                                                                    'text': license_plate_text,
                                                                    'bbox_score': score,
                                                                    'text_score': license_plate_text_score}}
                    cv2.putText(frame, license_plate_text, (xcar1, ycar1), cv2.FONT_HERSHEY_SIMPLEX, 4.3, (0, 255, 0), 2)
    frame = cv2.resize(frame, (1280, 720))
    cv2.imshow("OT", frame)
    if cv2.waitKey(1) == ord("q"):
        break

# write results
write_csv(results, './test.csv')