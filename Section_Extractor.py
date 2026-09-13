import re

Degree_Level_Markers = [r"المراحل الدراسية", r"المرحلة الدراسية"]
Fields_Markers = [r"التخصصات المتاحة", r"التخصصات المشمولة", r"التخصصات الأكثر طلب"]
Eligibility_Markers = [
    r"شروط التقديم", r"شروط الأهلية", r"معايير التقديم",
    r"معايير الأهلية", r"شروط المنحة", r"متطلبات التقديم",
]
Stop_Markers = [
    r"الأوراق المطلوبة", r"المستندات المطلوبة", r"خطوات التقديم",
    r"طريقة التقديم", r"كيفية التقديم", r"معايير الاختيار والتقييم",
    r"معلومات عامة", r"مزايا المنحة", r"نبذة عن",r"اطلع على",r"شروط استمرار",r"اكتشف"
]

All_Markers = Degree_Level_Markers + Fields_Markers + Eligibility_Markers + Stop_Markers

def is_line_start(text, pos):
    line_start = text.rfind("\n", 0, pos) + 1
    prefix = text[line_start:pos]
    return prefix.strip() == ""

def find_all_header_positions(text, markers):
    positions = []
    for marker in markers:
        for m in re.finditer(marker, text):
            if is_line_start(text, m.start()):
                positions.append((m.start(), m.end(), marker))
    positions.sort(key=lambda x: x[0])
    return positions


def extract_section_by_markers(text, target_markers, all_markers=All_Markers):
    all_positions = find_all_header_positions(text, all_markers)
    result_chunks = []

    for start_pos, end_pos, marker in all_positions:
        if marker not in target_markers:
            continue

        # نتخطى باقي سطر العنوان نفسه (مثلاً "المشمولة في المنحة") ونبدأ من السطر التالي
        newline_pos = text.find("\n", end_pos)
        content_start = newline_pos + 1 if newline_pos != -1 else end_pos

        section_end = len(text)
        for pos, _, other_marker in all_positions:
            if pos > start_pos and other_marker != marker:
                section_end = pos
                break

        chunk = text[content_start:section_end].strip()
        if chunk:
            result_chunks.append(chunk)

    return " ".join(result_chunks).strip()


def extract_key_sections(description):
    if not description:
        return ""
    degree_text = extract_section_by_markers(description, Degree_Level_Markers)
    fields_text = extract_section_by_markers(description, Fields_Markers)
    eligibility_text = extract_section_by_markers(description, Eligibility_Markers)

    combined_parts = []
    if degree_text:
        combined_parts.append(f"المراحل الدراسية: {degree_text}")
    if fields_text:
        combined_parts.append(f"التخصصات المتاحة: {fields_text}")
    if eligibility_text:
        combined_parts.append(f"شروط التقديم: {eligibility_text}")

    combined_text = "\n".join(combined_parts).strip()

    return combined_text if combined_text else description.strip()