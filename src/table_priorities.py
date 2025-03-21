import json

class TablePriorities:
    def __init__(self, file_path):
        self.file_path = file_path
        self.tables = self.load_tables()

    def load_tables(self):
        with open(self.file_path, 'r') as file:
            data = json.load(file)
        return data['tables'][0]

    def get_table_info(self, table_name):
        return self.tables.get(table_name, None)