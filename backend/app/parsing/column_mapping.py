# German-to-English column name mapping for the ERP tab-delimited export.
#
# v1.26 (2026-04-30): swapped to the 60-column "Aufträge" export format.
# Headers from the new export are listed below in source order; only the
# subset that maps to a column on `SalesRecord` is kept — unmapped headers
# (Land, EDI, MS, M Sperre, ES, Beleg Nr, LS / RG, Sperrkz, Erfolg %, GS,
# Ihr Datum, Ihre Zeichen, Telefonnummer, Telefaxnummer, TZ, Basis,
# Anteil 1..5, Vers.Nw., Vers.Nw. Datum, Anz.Druck, Kopfrabatt %,
# Zoll-Status, Zoll-MRN, MRN-Datum, STR-Status, User1, User2, Aktion, GBst,
# GBst-St, GBst-Art, Name 2, Name 3, Wert, brutto, Versand per Mail) are
# dropped at parse time.
#
# v1.44: "Benutzer" promoted from dropped → created_by_user; used as the rep
# field for orders/wk/rep (replaces the Kontakte bridge).
#
# Schema columns that the new format does NOT populate stay NULL:
# remaining_value, complexity_group, comment, business_area, delivery_date,
# requested_date, arrival_date, manual_lock, responsible_person, project_name,
# manual_status, material_flag, internal_processor_1/2, approval_comment_1/2,
# technical_check, purchase_check.

GERMAN_TO_ENGLISH: dict[str, str] = {
    "VRG": "erp_status_flag",       # "AUF" / "ANG" marker
    "Nummer": "order_number",        # Required
    "Datum": "order_date",
    "Adresse": "customer_id",
    "Name": "customer_name",
    "Ort": "city",
    "Wert": "total_value",
    "Status": "status_code",
    "Art": "order_type",
    "Typ": "order_subtype",
    "Frei1": "free_field_1",
    "Frei2": "free_field_2",
    "K Sperre": "customer_lock",
    "Projekt": "project_reference",
    "Bemerkung": "remark",
    "Komm. Endkunde": "end_customer_comment",
    "Lieferadresse": "delivery_address",
    "Lieferort": "delivery_city",
    "Bestellnummer": "vv_number",
    "Proj.Nr.": "project_number",
    "Benutzer": "created_by_user",
}

# English column names that contain DD.MM.YYYY dates.
DATE_COLUMNS: set[str] = {
    "order_date",
}

# English column names that contain German decimal numbers (. thousands, , decimal).
DECIMAL_COLUMNS: set[str] = {
    "total_value",
}

# English column names that map to Integer DB columns.
INTEGER_COLUMNS: set[str] = {
    "status_code",
    "customer_lock",
}

# English column names that must be non-empty.
REQUIRED_COLUMNS: set[str] = {
    "order_number",
}
