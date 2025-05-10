import sys
import os
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"sys.path: {sys.path}")

from dotenv import load_dotenv

# Add the project root to sys.path to allow for imports from processing and tasks
# Assumes the tests directory is directly under the project root (AR3)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the test function from the new file
from tests.test_video_processing import test_video_processing
from tests.test_frame_processing import test_frame_processing
from tests.test_end2end import test_end2end
from tests.upload_video import upload_video # Import the new upload_video function

if __name__ == "__main__":
    print("Executing tests from tests.py...")

    test_video_processing()
    test_frame_processing()


    
    
