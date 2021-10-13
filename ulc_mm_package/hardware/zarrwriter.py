import zarr

# ==================== Custom errors ===============================
class AttemptingWriteWithoutFile(Exception):
    def __str__(self):
        return """
        No zarr file has been made and a write is being attempted.
        Ensure that 'createNewFile(filename)' has been called before attempting
        to write an array.
        """

# ==================== Main class ===============================
class ZarrWriter():
    def __init__(self):
        self.store = None
        self.group = None
        self.arr_counter = 0

    def createNewFile(self, filename: str, overwrite: bool=False):
        """Create a new zarr file.
        
        Parameters
        ----------
        filename : str 
            Filename, don't include the extension (i.e pass "new_file" not "new_file.zip").
        overwrite : bool
            Will overwrite a file with the existing filename if it exists, otherwise will append.
                
        """
        try:
            filename = f"{filename}.zip"
            if overwrite:
                self.store = zarr.ZipStore(filename, mode='x')
            else:
                self.store = zarr.ZipStore(filename, mode='w')
            self.group = zarr.group(store=self.store)
            self.arr_counter = 0
        except AttributeError:
            raise IOError(f"Error creating {filename}.zip")

    def writeSingleArray(self, data):
        try:
            self.group.create_dataset(f"{self.arr_counter}", data=data)
            self.arr_counter += 1
        except Exception:
            raise AttemptingWriteWithoutFile()

    def closeFile(self):
        self.store.close()
        self.store = None

    def __del__(self):
        # If the user did not manually close the storage, close it
        if self.store != None:
            self.store.close()

if __name__ == "__main__":
    writer = ZarrWriter()
    writer.createNewFile("experiment1")
    writer.writeSingleArray([1, 2, 3])
    writer.closeFile()