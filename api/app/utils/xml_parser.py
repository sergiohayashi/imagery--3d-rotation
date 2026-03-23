import xml.etree.ElementTree as ET


def xml_to_dict(element):
    """Recursively converts an XML element and its children into a dictionary."""
    result = {}

    # print( 'xml to dict. element: ', element)
    # If the element has child elements
    if list(element):
        temp = {}
        for child in element:
            child_result = xml_to_dict(child)
            if child.tag in temp:
                # If the tag already exists, convert to a list
                if not isinstance(temp[child.tag], list):
                    temp[child.tag] = [temp[child.tag]]
                temp[child.tag].append(child_result[child.tag])
            else:
                temp.update(child_result)
        result[element.tag] = temp
    else:
        # If it's a leaf node, use its text
        result[element.tag] = element.text.strip() if element.text else None

    return result


def convert_xml_to_object(xml_string):
    print("xml_string:", xml_string)
    root = ET.fromstring(f"<root>{xml_string}</root>")
    d = xml_to_dict(root)
    return d["root"]


# ------------- Example usage ----------------
xml_text = """
<name>John Doe</name>
<age>30</age>
<emails>
    <email>john@example.com</email>
    <email>doe@example.com</email>
</emails>
"""

result = convert_xml_to_object(xml_text)
print(result)
