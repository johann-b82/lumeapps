# German-to-English column name mapping for ERP tab-delimited export files.
# Source: 38-column ERP export with German headers, confirmed from sample_export.csv.
# Column 2 has an empty German header — mapped to erp_status_flag.

GERMAN_TO_ENGLISH: dict[str, str] = {
    "Auftrag": "order_number",
    "": "erp_status_flag",
    "Datum": "order_date",
    "Kunde": "customer_id",
    "Name": "customer_name",
    "Ort": "city",
    "Restwert": "remaining_value",
    "Art": "order_type",
    "Typ": "order_subtype",
    "Kompl. Grp": "complexity_group",
    "Kommentar": "comment",
    "VV-Nr.": "vv_number",
    "Lieferdatum": "delivery_date",
    "GS Bereich": "business_area",
    "Projekt": "project_reference",
    "Lieferadresse": "delivery_address",
    "Lieferort": "delivery_city",
    "Gesamtwert": "total_value",
    "Sperre manuell": "manual_lock",
    "Verantwortlich": "responsible_person",
    "Frei 1": "free_field_1",
    "Frei 2": "free_field_2",
    "Bemerkung": "remark",
    "Projekt Nr.": "project_number",
    "Projektname": "project_name",
    "man.Status": "manual_status",
    "K Sperre": "customer_lock",
    "Mat": "material_flag",
    "Kom. Endkunde": "end_customer_comment",
    "1. Bearbeiter, intern": "internal_processor_1",
    "2. Bearbeiter, intern": "internal_processor_2",
    "Kommentar zu Freigabe 1": "approval_comment_1",
    "Status": "status_code",
    "Wunschdatum": "requested_date",
    "Tech Pr\u00fcf": "technical_check",
    "Kauf Pr\u00fcf": "purchase_check",
    "Kommentar zu Freigabe 2": "approval_comment_2",
    "Eintreffdatum": "arrival_date",
}

# English column names that contain DD.MM.YYYY dates (per D-10)
DATE_COLUMNS: set[str] = {
    "order_date",
    "delivery_date",
    "requested_date",
    "arrival_date",
}

# English column names that contain German decimal numbers (per D-04, D-06)
DECIMAL_COLUMNS: set[str] = {
    "remaining_value",
    "total_value",
}

# English column names that map to Integer DB columns
INTEGER_COLUMNS: set[str] = {
    "business_area",
    "manual_status",
    "customer_lock",
    "status_code",
}

# English column names that must be non-empty per D-12 check 4
REQUIRED_COLUMNS: set[str] = {
    "order_number",
}
