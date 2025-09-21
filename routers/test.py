import os
import json
import logging

logger = logging.getLogger(__name__)

def get_commentaries_and_sanskrit(input_text: str):
    """
    Go through every file in the commentaries_and_sanskrit folder and print every object inside it.
    """


    commentaries_dir = os.path.join(os.path.dirname(__file__), "..", "commentaries_and_sanskrit")

    # List all files in the directory
    try:
        files = [f for f in os.listdir(commentaries_dir) if f.endswith('.json')]
    except Exception as e:
        logger.error(f"Error listing files in directory {commentaries_dir}: {str(e)}")
        return

    for json_file in files:
        file_path = os.path.join(commentaries_dir, json_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for entry in data:
                root_display_text = entry.get("root_display_text", "")
                print(root_display_text)
            
        except FileNotFoundError:
            logger.warning(f"Commentary file not found: {file_path}")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON file: {file_path}")
        except Exception as e:
            logger.error(f"Error reading commentary file {file_path}: {str(e)}")

if __name__ == "__main__":
    get_commentaries_and_sanskrit("This is a test input text")