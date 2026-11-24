"""Course migration from another LMS (decisions/108).

A Common Cartridge (``.imscc``) or a Moodle 5.0–5.3 backup (``.mbz``) is read into a
Course Pack manifest in memory and imported into an empty Course Schedule by the
Course Pack importer (decisions/041). ``export_cc`` writes the reverse."""
