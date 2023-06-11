import os
import csv
import argparse
from ofxtools import OFXTree


def rewrite_qfx(input_file: str, output_file: str, rules: dict) -> None:
    tree = OFXTree()
    tree.parse(input_file)
    root = tree.getroot()

    # Store values not found to output new rules
    missing_values = set()

    transaction_name_elements = root.findall(".//STMTTRN/NAME")
    for element in transaction_name_elements:
        name = element.text

        # Find matching rule
        match = None
        for search, replace in rules.items():
            if search in name:
                if match != None:
                    raise ValueError(f'Multiple matches found for name {name}')
                match = (search, replace)

        # Replace with the matching rule if applicable
        if match is not None:
            _, replace = match

            # Handle special cases
            if replace == "<NO_CHANGE>":
                print(f'Ignoring "{name}" due to no change tag.')
            else:
                print(f'Replacing "{name}" with "{replace}')
                element.text = replace

        else:
            print(f'Not Found - default from {name} to {name.title()}')
            missing_values.add(name)
            element.text = name.title()
    
    tree.write(output_file)
    print(f'Wrote to {output_file} successfully.')

    if missing_values:
        print('Add the following to your rules list:')
        for value in missing_values:
            print(f'"{value}","replacement"')


def read_rules(rules_file: str) -> dict:
    rules_dictionary = {}

    with open(rules_file, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            rules_dictionary[row['SearchText']] = row['Replacement']
    
    return rules_dictionary


if __name__ == "__main__":
    # Parse arguments
    parser = argparse.ArgumentParser(description='Rewrite QFX file to use better names.')
    parser.add_argument('input_file')
    args = parser.parse_args()

    # Read rules file
    if not os.path.exists('rules.csv'):
        raise FileNotFoundError('No rules.csv file has been defined, please see example_rules.csv')
    rules = read_rules('rules.csv')

    # Get new output file
    filename, ext = os.path.splitext(args.input_file)
    output_file = filename + '_modified' + ext
    rewrite_qfx(args.input_file, output_file, rules)
