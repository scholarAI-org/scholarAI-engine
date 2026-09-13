import json


def Compact_List_Encoder(obj, indent=2):
    def format_value(value, current_indent):
        if isinstance(value, list):
            return json.dumps(value, ensure_ascii=False)
        elif isinstance(value, dict):
            return format_dict(value, current_indent + indent)
        else:
            return json.dumps(value, ensure_ascii=False)

    def format_dict(d, current_indent):
        if not d:
            return "{}"
        pad = " " * current_indent
        closing_pad = " " * (current_indent - indent)
        items = []
        for k, v in d.items():
            formatted_value = format_value(v, current_indent)
            items.append(f'{pad}"{k}": {formatted_value}')
        return "{\n" + ",\n".join(items) + "\n" + closing_pad + "}"

    if isinstance(obj, list):
        pad = " " * indent
        items = [format_dict(item, indent + indent) if isinstance(item, dict) else format_value(item, indent) for item in obj]
        return "[\n" + ",\n".join(f"{pad}{item}" for item in items) + "\n]"
    return format_dict(obj, indent)