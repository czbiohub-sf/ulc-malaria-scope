from datetime import datetime
import csv
import argparse

# Number of times to repeat a barcode in the csv
# This is done since we package (32 / NUM REPETITIONS) together
# So for example, since we are storing 8 flow cells per tube
# We need 4 of each unique ID to label a full-sheet
NUM_REPETITIONS = 4

def luhn_checksum(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = 0
    checksum += sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d*2))
    return checksum % 10

def is_luhn_valid(card_number):
    return luhn_checksum(card_number) == 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("lower_bound", help="Lower bound (inclusive)", type=int)
    parser.add_argument("upper_bound", help="Upper bound (inclusive)", type=int)
    args = parser.parse_args()

    lb, ub = args.lower_bound, args.upper_bound
    filename = f"{datetime.now().strftime('%Y-%m-%d')}_msfc_ids_{lb}-{ub}.csv"
    print(f"{'='*10}")
    print(f"There are {int(0.1*(ub-lb))} Luhn-verifiable numbers between [{lb}, {ub}].")
    input(f"{filename} will be created. Press enter to continue.\n{'='*10}")

    with open(f"{filename}", "w") as csvfile:
        writer = csv.writer(csvfile)
        header = ['flowcell-id']
        writer.writerow(header)

        for i in range(lb, ub + 1):
                if is_luhn_valid(i):
                    for _ in range(4):
                        writer.writerow([f"{i:04}"])
    print("Done! Enjoy your numbers.")
    
if __name__ == "__main__":
    main()