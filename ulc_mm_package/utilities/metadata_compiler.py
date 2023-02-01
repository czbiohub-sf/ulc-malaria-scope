from ulc_mm_package.scope_constants import SSD_DIR, SSD_NAME

def metadata_compiler():

	# Get metadata directory
    metadata_dir = path.join(SSD_DIR, SSD_NAME)
    if path.exists(metadata_dir):
        self.ext_dir = metadata_dir + "/"
    else:
        print(
            f"Could not find '{SSD_NAME}' in {SSD_DIR}. Searching for other folders in this directory."
        )
        try:
            self.ext_dir = SSD_DIR + listdir(SSD_DIR)[0] + "/"
        except (FileNotFoundError, IndexError) as e:
            print(
                f"Could not find any folders within {SSD_DIR}."
            )
            return
    print(f"Getting data from {self.ext_dir}")

if __name__ == "__main__":
	metadata_compiler()
