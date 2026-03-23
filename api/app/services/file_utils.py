import os


class FileUtils:

    @staticmethod
    def safe_delete(file_path):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}", e)

    @staticmethod
    def getsize(file_path):
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
        return 0
