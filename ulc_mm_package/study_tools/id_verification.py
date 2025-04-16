"""
A set of ID verification functions to ensure that the entered participant ID matches
what is expected for a given field study.

These functions are used in `form_gui.py` to validate the `participant_id` field.
"""

import inspect
import logging
import os

logger = logging.getLogger()


def luhn_checksum(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]

    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = 0
    checksum += sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10


def is_luhn_valid(card_number):
    return luhn_checksum(card_number) == 0


def _select_validation_function() -> callable:
    """Selects the validation function to use based on an environment variable which is unique for a field study.

    Important: The onus is on us to ensure that the environment variable is set on a machine prior to starting a study.

    This function relies on the field study name to automatically find the corresponding validation function.

    All validation functions MUST follow the naming convention:
    - `{FIELD_STUDY_NAME}_barcode_validation`
    where `{field_study_name}` is the name of the field study (e.g. `rwanda_phase_2`).
    """
    field_study_name = os.environ.get("FIELD_STUDY_NAME")

    # Field study name hasn't been set in the environment, so all participant IDs are valid
    if field_study_name is None:
        logger.info(
            "The FIELD_STUDY_NAME environment variable is not set. All participant IDs will be considered valid."
        )
        return lambda _: True

    available_functions = [
        (name, func)
        for name, func in globals().items()
        if inspect.isfunction(func) and name.endswith("_barcode_validation")
    ]

    for name, func in available_functions:
        if field_study_name == name.split("_barcode_validation")[0]:
            logger.info(
                f"Using validation function {name} for participant ID validation."
            )
            return func
    raise ValueError(
        f"The FIELD_STUDY_NAME environment variable is set to {field_study_name}, but no corresponding validation function was found in `id_verification.py`."
        "Double check that the function name exactly matches the field study name. Alternately, unset the environment variable via `unset FIELD_STUDY_NAME` (and possibly removing it from `~/.bashrc` if it is there)."
    )


def rwanda_phase_2_barcode_validation(participant_id: str) -> tuple[bool, str]:
    """Validates the participant ID for the Rwanda Phase 2 field study.

    The codes used for this study must adhere to the following requirements:
    - Follows the format {XXX}-{YYYYY} where
    - XXX is a three-digit, Luhn verifiable number that denotes the sample collection location
    - YYYYY is a five-digit, Luhn verifiable number that denotes the participant ID

    Parameters
    ----------
    participant_id: str
        The participant ID to validate (passed in from the form's participant_id text field).

    Returns
    -------
    tuple[bool, str]
        Returns a tuple where the first element is a boolean indicating whether the participant ID is valid or not,
        and the second element is a string indicating the expected format of the participant ID.
    """
    expected_format = "XXX-YYYYY"

    if "-" not in participant_id:
        return False, expected_format

    location_code, participant_code = participant_id.split("-")

    # Verify string length
    if len(location_code) != 3 or len(participant_code) != 5:
        return False, expected_format

    # Verify that the location code and participant code are both numeric
    if not location_code.isdigit() or not participant_code.isdigit():
        return False, expected_format

    # Verify that the location code and participant code are both Luhn verifiable
    if not is_luhn_valid(location_code) or not is_luhn_valid(participant_code):
        return False, expected_format

    return True, expected_format


if __name__ == "__main__":
    pass
