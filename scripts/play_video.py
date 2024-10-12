import cv2

# Path to your video file
video_path = r'C:\Users\dahern\Documents\RYZE.AI\fastapi\video\test1.mp4'

# Open the video file
cap = cv2.VideoCapture(video_path)

# Check if the video file opened successfully
if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

# Loop through the video frames
while True:
    # Read a frame
    ret, frame = cap.read()
    
    # If the frame was not read successfully, end the loop
    if not ret:
        print("End of video.")
        break
    
    # Display the frame
    cv2.imshow('MP4 Video', frame)
    
    # Press 'q' on the keyboard to exit the video early
    if cv2.waitKey(25) & 0xFF == ord('q'):
        break

# Release the video capture object and close any OpenCV windows
cap.release()
cv2.destroyAllWindows()
