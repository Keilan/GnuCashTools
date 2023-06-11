# QFX Parser
This tool iterates through a QFX file and renames transactions based on a list of rules, this should make it easier to import the QFX file into GnuCash.

## Notes
* A replacement value in all capitals indicates that it requires manual work because the same name is used for multiple transacations.
* A replacement value in angle brackets is a special instruction, such as:
    * <NO_CHANGE> - Leave the original name alone