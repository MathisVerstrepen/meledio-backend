import json

def unload_json(json_data: str) -> dict:
    """ Unload JSON data 

    Args:
        json_data (str): JSON data to unload

    Returns:
        dict: Unloaded JSON data or None if error occured
    """
    
    try:
        return json.loads(json_data)
    except json.JSONDecodeError:
        print("Erreur lors de la conversion de la réponse en JSON.")
        return None