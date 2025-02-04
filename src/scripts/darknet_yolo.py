import os
import cv2
import numpy as np

ROOT_DIR = os.path.dirname(__file__)

class DarknetDNN:
    def __init__(self, dnn_model = "weights/yolov3-tiny.weights", dnn_config = "cfg/yolov3-tiny.cfg"):
        #Check the installed OpenCV version
        print("Loading on OpenCV version", cv2.__version__)

        #Initiate DNN model using Darknet framework
        print("Initiating Darknet ...")
        self.dnn_model = os.path.join(ROOT_DIR, dnn_model)
        self.dnn_config = os.path.join(ROOT_DIR, dnn_config)
        self.dnn_name_lists = os.path.join(ROOT_DIR, "coco.names")
        print("Loading model from ", self.dnn_model)
        print("Loading config from ", self.dnn_config)
        print("Loading names from ", self.dnn_name_lists)
        self.net = cv2.dnn.readNet(self.dnn_model, self.dnn_config)
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)

        self.classes = []

        with open(self.dnn_name_lists, "r") as f:
            self.classes = [line.strip() for line in f.readlines()]
        
        self.layer_names = self.net.getLayerNames()
        #self.colors = np.random.uniform(0, 255, size=(len(self.classes), 3))

        #Check the type of output layer, some older version OpenCV has a different type of output layer
        print("Output layer type is", type(self.net.getUnconnectedOutLayers()[0]))
        if isinstance(self.net.getUnconnectedOutLayers()[0], np.int32):
            self.output_layers = [self.layer_names[i - 1] for i in self.net.getUnconnectedOutLayers()]
        else:
            self.output_layers = [self.layer_names[i[0] - 1] for i in self.net.getUnconnectedOutLayers()]

        #Blob parameter
        self.blob_scalefactor = 1/255.0
        self.blob_size = (320, 320)
        self.blob_scalar = (0, 0, 0)
        self.blob_swapRB = True
        self.blob_crop = False
        self.blob_ddepth = cv2.CV_32F

        #Threshold for detecting object
        self.confidence_threshold = 0.3
        self.nms_threshold = 0.4

    def detect_object(self, image):
        #Pre-process the input image
        height, width, channels = image.shape
        blob = cv2.dnn.blobFromImage(image, self.blob_scalefactor, self.blob_size, self.blob_scalar, self.blob_swapRB, self.blob_crop, self.blob_ddepth)

        #Pass the blob as input into the DNN
        self.net.setInput(blob)

        #Wait for the output
        output = self.net.forward(self.output_layers)

        #Detected object information
        self.object_classes = []
        self.object_confidences = []
        self.object_boxes = []
        self.object_area = []
        self.object_position = []

        #For every output of the DNN
        for out in output:
            #For every detection in output
            for detection in out:
                #Takes the detection scores
                scores = detection[5:]

                #The object id detected is the largest scores
                class_id = np.argmax(scores)

                #The confidence of the detected object is the scores of the detected object
                confidence = scores[class_id]

                #Filter out if the object has low confidence
                if confidence <= self.confidence_threshold:
                    continue

                #Filter out non-human object
                if class_id != 0:
                    continue

                #Get the location of the detected object in the frame input
                cx = int(detection[0] * width)
                cy = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                x1 = int(cx - w/2)
                y1 = int(cy - h/2)
                x2 = int(cx + w/2)
                y2 = int(cy + h/2)
                area = (w * h)

                #Save the information about the detected object
                self.object_classes.append(class_id)
                self.object_confidences.append(confidence)
                self.object_boxes.append([x1, y1, x2, y2])
                self.object_area.append(area)
                
                position = 'Center'
                if cx <= width/3:
                    position = 'Left'
                elif cx >= 2 * width/3:
                    position = 'Right'
                
                self.object_position.append(position)
    
    def draw_detected_object(self, frame, depth_frame = None):
        #Perform Non-Maximum Suppression to remove the redundant detections
        indexes = cv2.dnn.NMSBoxes(self.object_boxes, self.object_confidences, self.confidence_threshold, self.nms_threshold)
        for i in indexes:
            #i = i[0]
            x1, y1, x2, y2 = self.object_boxes[i]
            label = self.classes[self.object_classes[i]]
            color = (0, 255, 0)

            cx = int((x1 + x2)/2)
            cy = int((y1 + y2)/2)

            this_position = self.object_position[i]

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)

            text_size, _ = cv2.getTextSize(label.capitalize(), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (x1 + 5, y1 + 5), (x1 + 5 + text_size[0], y1 + 5 - text_size[1]), (0,0,0), cv2.FILLED)
            cv2.putText(frame, label.capitalize(), (x1 + 5, y1 + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            cv2.putText(frame, this_position, (x1+5, y1+50), 0, 0.8, (255, 255, 255), 2)
            
            if depth_frame is not None:
                distance = round(depth_frame.get_distance(cx, cy), 2)
                text_size, _ = cv2.getTextSize(f"{distance} m", cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (x1 + 5, y1 + 25), (x1 + 5 + text_size[0], y1 + 25 - text_size[1]), (0,0,0), cv2.FILLED)
                cv2.putText(frame, f"{distance} m", (x1 + 5, y1 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    
    def get_command(self):
        if not self.object_area:
            return 'Hold'
        else:
            return self.object_position[self.object_area.index(max(self.object_area))]
    
    def detect_with_color(self, image, low_hsv, high_hsv):
        # Pre-process the input image
        height, width, channels = image.shape
        blob = cv2.dnn.blobFromImage(image, self.blob_scalefactor, self.blob_size, self.blob_scalar, self.blob_swapRB, self.blob_crop, self.blob_ddepth)

        # Pass the blob as input into the DNN
        self.net.setInput(blob)

        # Wait for the output
        output = self.net.forward(self.output_layers)

        # Detected object information
        #object_classes = []
        object_confidences = []
        object_boxes = []

        # For every output of the DNN
        for out in output:
            # For every detection in output
            for detection in out:
                # Takes the detection scores
                scores = detection[5:]

                # The object id detected is the largest scores
                class_id = np.argmax(scores)

                # The confidence of the detected object is the scores of the detected object
                confidence = scores[class_id]

                # Filter out if the object has low confidence
                if confidence <= self.confidence_threshold:
                    continue

                # Filter out non-human object
                if class_id != 0:
                    continue

                # Get the location of the detected object in the frame input
                cx = int(detection[0] * width)
                cy = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                x1 = int(cx - w/2)
                y1 = int(cy - h/2)
                x2 = int(cx + w/2)
                y2 = int(cy + h/2)

                # Save the information about the detected object
                #self.object_classes.append(class_id)
                object_confidences.append(confidence)
                object_boxes.append([x1, y1, x2, y2])
        
        # Perform Non-Maximum Suppression to remove the redundant detections
        indexes = cv2.dnn.NMSBoxes(object_boxes, object_confidences, self.confidence_threshold, self.nms_threshold)
        color_area = []
        output_box = []
        for i in indexes:
            x_1, y_1, x_2, y_2 = object_boxes[i]
            color = (0, 255, 0)

            # Check the color of the person
            ## Take the roi of our detected human
            roi = image[y_1:y_2, x_1:x_2]
            roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

            ## Apply color filtering to the object
            mask = cv2.inRange(roi, low_hsv, high_hsv)

            ## Find the contours of the color
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            ## Calculate the Area
            total_area = 0
            for contour in contours:
                area = cv2.contourArea(contour)
                total_area += area

            ## Save the area
            color_area.append(total_area)
            output_box.append([x_1, y_1, x_2, y_2])
        
        return color_area, output_box
    
    def draw_target(self, frame, color_area, output_box):
        target_list = list(zip(color_area, output_box))
        sorted_target_list = sorted(target_list, key=lambda x: x[0], reverse=True)

        area, bbox = zip(*sorted_target_list)
        for i, (area, bbox) in sorted_target_list:
            color_area = area
            x1, y1, x2, y2 = bbox
            
            if i == 0:
                color = (0, 255, 0)
            else:
                color = (0, 0, 255)
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)
            
        return frame
    
    def detect_human(self, image):
        #Pre-process the input image
        height, width, channels = image.shape
        blob = cv2.dnn.blobFromImage(image, self.blob_scalefactor, self.blob_size, self.blob_scalar, self.blob_swapRB, self.blob_crop, self.blob_ddepth)

        #Pass the blob as input into the DNN
        self.net.setInput(blob)

        #Wait for the output
        output = self.net.forward(self.output_layers)

        #Detected object information
        #self.object_classes = []
        self.object_confidences = []
        self.object_boxes = []
        #self.object_area = []
        self.object_position = []

        #For every output of the DNN
        for out in output:
            #For every detection in output
            for detection in out:
                #Takes the detection scores
                scores = detection[5:]

                #The object id detected is the largest scores
                class_id = np.argmax(scores)

                #The confidence of the detected object is the scores of the detected object
                confidence = scores[class_id]

                #Filter out if the object has low confidence
                if confidence <= self.confidence_threshold:
                    continue

                #Filter out non-human object
                if class_id != 0:
                    continue

                #Get the location of the detected object in the frame input
                cx = int(detection[0] * width)
                cy = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                x1 = int(cx - w/2)
                y1 = int(cy - h/2)
                x2 = int(cx + w/2)
                y2 = int(cy + h/2)
                area = (w * h)

                #Save the information about the detected object
                #self.object_classes.append(class_id)
                self.object_confidences.append(confidence)
                self.object_boxes.append([x1, y1, x2, y2])
                #self.object_area.append(area)
                
                position = 'Center'
                if cx <= width/3:
                    position = 'Left'
                elif cx >= 2 * width/3:
                    position = 'Right'
                
                self.object_position.append(position)
        
        output_bbox = []
        output_confidences = []
        output_position = []

        #Perform Non-Maximum Suppression to remove the redundant detections
        indexes = cv2.dnn.NMSBoxes(self.object_boxes, self.object_confidences, self.confidence_threshold, self.nms_threshold)
        for i in indexes:
            #i = i[0]
            #x1, y1, x2, y2 = self.object_boxes[i]
            output_bbox.append(self.object_boxes[i])
            output_confidences.append(self.object_confidences[i])
            output_position.append(self.object_position[i])

            cx = int((x1 + x2)/2)
            cy = int((y1 + y2)/2)

        return output_bbox, output_confidences, output_position
    
    def draw_human_info(self, frame, bbox, confidences, positions, areas):
        for box, confidence, position, area in zip(bbox, confidences, positions, areas):
            x1, y1, x2, y2 = box
            confidence_value = confidence
            position_in_frame = position
            color_conf = area

            font = cv2.FONT_HERSHEY_SIMPLEX

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 1)
            text_size, _ = cv2.getTextSize(f"{confidence_value:.2f}", font, 0.5, 1)
            cv2.rectangle(frame, (x1 + 5, y1 + 5), (x1 + 5 + text_size[0], y1 + 5 - text_size[1]), (0, 0, 0), cv2.FILLED)
            cv2.putText(frame, f"{confidence_value:.2f}", (x1 + 5, y1 + 5), font, 0.5, (0, 255, 0), 1)
            text_size_2, _ret = cv2.getTextSize(position_in_frame, font, 0.5, 1)
            cv2.rectangle(frame, (x1 + 5, y1 + 5 + text_size[1]), (x1 + 5 + text_size_2[0], y1 + 5 + text_size[1] - text_size_2[1]), (0, 0, 0), cv2.FILLED)
            cv2.putText(frame, position_in_frame, (x1 + 5, y1 + 5 + text_size[1]), font, 0.5, (0, 255, 0), 1)
            text_size_3, _ret2 = cv2.getTextSize(f"{color_conf}", font, 0.5, 1)
            cv2.rectangle(frame, (x1 + 5, y1 + 5 + text_size[1] + text_size_2[1]), (x1 + 5 + text_size_3[0], y1 + 5 + text_size[1] + text_size_2[1] - text_size_3[1]), (0, 0, 0), cv2.FILLED)
            cv2.putText(frame, f"{color_conf}", (x1 + 5, y1 + 5 + text_size[1] + text_size_2[1]), font, 0.5, (0, 255, 0), 1)

    def check_color(self, image, bbox, low_hsv, upp_hsv):
        areas = []
        for box in bbox:
            x1, y1, x2, y2 = box

            if x1 < 0:
                x1 = 0
            if x2 > 640:
                x2 = 640
            if y1 < 0:
                y1 = 0
            if y2 > 480:
                y2 = 480

            roi = image[y1:y2, x1:x2]
            roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

            mask = cv2.inRange(roi, low_hsv, upp_hsv)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            total_area = 0
            for contour in contours:
                area = cv2.contourArea(contour)
                total_area += area
            
            areas.append(total_area)
        
        return areas
    
    def hunt(self, frame, depth, bbox, confidences, postitions, areas):
        # Check if the bbox is empty or not
        if not bbox:
            return 
        
        # Get the maximum color
        max_areas = max(areas)
        max_index = areas.index(max_areas)

        # Get the target info
        x1, y1, x2, y2 = bbox[max_index]
        confidence = confidences[max_index]
        postition = postitions[max_index]
        distance = None
        cx = int((x1 + x2)/2)
        cy = int((y1 + y2)/2)

        # Check if depth exist
        if depth:
            distance = round(depth[cy,cx]/10)

        # Draw the info
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 1)
        text_size, _ret2 = cv2.getTextSize(f"Distance: {distance} cm", font, 0.5, 1)
        cv2.rectangle(frame, (cx, cy + text_size[1]), (cx, cy + text_size[1] ), (0, 0, 0), cv2.FILLED)
        cv2.putText(frame, f"Distance: {distance} cm", (cx, cy + text_size[1]), font, 0.5, (0, 255, 0), 1)
        return 
        

def main():
    net = DarknetDNN()
    cap = cv2.VideoCapture(4)

    while True:
        _, frame = cap.read()

        net.detect_object(frame)
        net.draw_detected_object(frame)

        cv2.imshow("Video", frame)

        #exit condition
        key = cv2.waitKey(1)
        if key == 27:
            print(f"Key {key} is pressed.")
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()