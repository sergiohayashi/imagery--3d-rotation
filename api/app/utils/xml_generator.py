import xml.etree.ElementTree as ET
from xml.dom import minidom


def dict_to_xml(tag, data):
    """
    Convert a Python dictionary into an XML Element.
    tag: root tag name
    data: dictionary or value
    """
    elem = ET.Element(tag)

    # If it's a dictionary, process children
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, list):
                # If value is a list, create a child element for each item
                for item in val:
                    child = dict_to_xml(key, item)
                    elem.append(child)
            else:
                # Normal nested dictionary or leaf value
                child = dict_to_xml(key, val)
                elem.append(child)
    else:
        # If it's a simple value, assign it as text
        elem.text = str(data)

    return elem


def convert_object_to_xml(obj):
    """
    Expects a dictionary with a single root key.
    """
    if len(obj) != 1:
        raise ValueError("Object must have exactly one root element.")
    root_tag = next(iter(obj))
    root_element = dict_to_xml(root_tag, obj[root_tag])

    # Pretty print the XML
    rough_string = ET.tostring(root_element, encoding="unicode")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")
