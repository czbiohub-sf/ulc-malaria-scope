import sys
import traceback

def main():
    def shutoff_excepthook(type, value, tb):
        # sys.__excepthook__(type, value, traceback)
        tbf = "".join(traceback.format_exception(value))
        # tbf = traceback.format_exception(type, value, tb)
        print(f"Oracle shutoff due to exception - {tbf}")

        sys.exit(1)

    sys.excepthook = shutoff_excepthook
    print(1/0)



if __name__ == "__main__":
    main()