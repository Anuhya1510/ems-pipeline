import pandas as pd

class EmsExtractor:
    def __init__(self, file_path):
        self.file_path = file_path

    def to_dataframe(self):
        return pd.read_csv(self.file_path)