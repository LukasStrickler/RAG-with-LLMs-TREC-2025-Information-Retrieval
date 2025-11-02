import sys
import os
import inspect
import re
import importlib
import pkgutil
from typing import Any, Dict, List, Set, Tuple, Type
from enum import Enum
from pydantic import BaseModel

# Add project root to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'shared', 'src'))

def discover_models_and_enums() -> Tuple[List[Tuple[str, Type[BaseModel]]], List[Tuple[str, Type[Enum]]]]:
    """Automatically discover all Pydantic models and enums from the shared package.
    
    Returns:
        Tuple containing:
        - List of (name, model_class) tuples for Pydantic models
        - List of (name, enum_class) tuples for Enums
    """
    models = []
    enums = []
    
    try:
        # Import the shared package
        import shared
        
        # Walk through all modules in the shared package
        for importer, modname, ispkg in pkgutil.walk_packages(shared.__path__, shared.__name__ + "."):
            try:
                module = importlib.import_module(modname)
                
                # Find all classes in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # Skip if it's not defined in this module (imported from elsewhere)
                    if obj.__module__ != modname:
                        continue
                    
                    # Protect against TypeError from issubclass with special types
                    if not isinstance(obj, type):
                        continue
                    
                    try:
                        # Check if it's a Pydantic model
                        if issubclass(obj, BaseModel) and obj != BaseModel:
                            models.append((name, obj))
                        
                        # Check if it's an enum
                        elif issubclass(obj, Enum) and obj != Enum:
                            enums.append((name, obj))
                    except TypeError:
                        # Skip generic aliases or special forms that can't be used with issubclass
                        continue
                        
            except Exception as e:
                print(f"Warning: Could not import module {modname}: {e}", file=sys.stderr)
                continue
                
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure the shared package is properly installed")
        sys.exit(1)
    
    return models, enums


def generate_enum_definitions(enums: List[Tuple[str, Type[Enum]]]) -> None:
    """Generate PlantUML enum definitions."""
    if enums:
        print('package "Enums" {')
        for name, enum in enums:
            print(f"  enum {name} {{")
            for member_name, member_value in enum.__members__.items():
                print(f"    {member_name}")
            print(f"  }}")
        print("}")
        print("")


def extract_relationships(models: List[Tuple[str, Type[BaseModel]]]) -> Set[str]:
    """Extract relationships from model fields."""
    relationships = set()

    for name, model in models:
        if hasattr(model, "model_fields"):
            for field_name, field_info in model.model_fields.items():
                field_type = str(field_info.annotation)

                # Extract relationship information from field types
                if "shared." in field_type:
                    # Extract the related class name - handle various formats
                    related_class = field_type.split(".")[-1]
                    # Clean up the class name
                    related_class = (
                        related_class.replace(">", "")
                        .replace("'", "")
                        .replace("]", "")
                        .replace("[", "")
                    )
                    if related_class and related_class not in [
                        "str",
                        "int",
                        "float",
                        "bool",
                        "None",
                    ]:
                        # Special cases for aggregation relationships
                        if name == "RetrievalRun" and related_class in [
                            "RetrievalRequest",
                            "RetrievalResponse",
                        ]:
                            relationships.add(f"{name} o-- {related_class}")
                        else:
                            # Determine relationship type based on field type
                            if "List[" in field_type:
                                # List fields are composition (strong ownership)
                                relationships.add(f"{name} *-- {related_class}")
                            else:
                                # Single fields are composition (strong ownership)
                                relationships.add(f"{name} *-- {related_class}")

                # Also check for List[shared.Class] and Optional[shared.Class] patterns
                list_pattern = r"List\[shared\.(\w+)\]"
                optional_pattern = r"Optional\[shared\.(\w+)\]"

                list_match = re.search(list_pattern, field_type)
                if list_match:
                    relationships.add(f"{name} *-- {list_match.group(1)}")

                optional_match = re.search(optional_pattern, field_type)
                if optional_match:
                    relationships.add(f"{name} *-- {optional_match.group(1)}")

    return relationships


def generate_model_definitions(models: List[Tuple[str, Type[BaseModel]]]) -> None:
    """Generate PlantUML class definitions."""
    for name, model in models:
        print(f"class {name} {{")

        # Add fields
        if hasattr(model, "model_fields"):
            for field_name, field_info in model.model_fields.items():
                field_type = str(field_info.annotation)

                # Simplify type names for display
                field_type = field_type.replace("typing.", "").replace(
                    "typing_extensions.", ""
                )
                field_type = field_type.replace("typing.List", "List").replace(
                    "typing.Optional", "Optional"
                )
                field_type = field_type.replace("typing.Dict", "Dict").replace(
                    "typing.Union", "Union"
                )
                field_type = field_type.replace("pydantic.networks.", "")
                
                # Handle enum types FIRST - before other replacements that might break the format
                # Enum annotation format: "<enum 'IndexKind'>" or "<enum 'shared.enums.IndexKind'>"
                import re
                enum_pattern = r"<enum\s+'([^']+)'>"
                enum_was_processed = False
                if re.search(enum_pattern, field_type):
                    matches = re.findall(enum_pattern, field_type)
                    for enum_path in matches:
                        # Take last part after dot and add enum_ prefix for clarity
                        enum_name = enum_path.split(".")[-1]
                        # Replace the complete enum pattern with prefixed name
                        field_type = re.sub(r"<enum\s+'" + re.escape(enum_path) + r"'>", f"enum_{enum_name}", field_type)
                        enum_was_processed = True
                
                # Now do class replacements after enum handling, but skip if enum was processed
                if not enum_was_processed:
                    field_type = field_type.replace("<class '", "").replace("'>", "")
                
                # Detect Dict/dict types BEFORE list conversion
                is_dict_type = False
                if "Dict[" in field_type or "dict[" in field_type:
                    is_dict_type = True
                
                # Handle Literal types - convert to str (Literal is a constrained string type)
                if "Literal[" in field_type:
                    # Extract values from Literal for documentation if needed, but use str type
                    # Format: Literal["value1", "value2", ...]
                    field_type = "str"
                
                # Handle complex types (Dict or List)
                if "[" in field_type and "]" in field_type:
                    # Extract the inner types
                    start_idx = field_type.find("[")
                    end_idx = field_type.find("]")
                    inner_content = field_type[start_idx+1:end_idx]
                    
                    if is_dict_type:
                        # Dict[K, V] or dict[K, V] -> map<K, V>
                        # Parse key and value types
                        if "," in inner_content:
                            key_type, value_type = inner_content.split(",", 1)
                            # Clean up types
                            key_type = key_type.strip()
                            value_type = value_type.strip()
                            # Remove shared module prefixes
                            if "shared." in key_type:
                                key_type = key_type.split(".")[-1]
                            if "shared." in value_type:
                                value_type = value_type.split(".")[-1]
                            if "." in key_type and not key_type.startswith("shared."):
                                key_type = key_type.split(".")[-1]
                            if "." in value_type and not value_type.startswith("shared."):
                                value_type = value_type.split(".")[-1]
                            field_type = f"map<{key_type}, {value_type}>"
                        else:
                            # Fallback if parsing fails
                            field_type = "map"
                    else:
                        # List[T] -> list[T]
                        inner_type = inner_content
                        # Clean up any remaining shared module references
                        if "shared." in inner_type:
                            inner_type = inner_type.split(".")[-1]
                        elif "." in inner_type:
                            # Handle cases like "retrieval.config.TrecRunRow" -> "TrecRunRow"
                            inner_type = inner_type.split(".")[-1]
                        field_type = f"list[{inner_type}]"
                else:
                    # Clean up shared module references - take last part after any dots
                    if "shared." in field_type:
                        field_type = field_type.split(".")[-1]
                
                print(f"  +{field_name}: {field_type}")

        print("}")
        print("")


def generate_uml() -> None:
    """Main UML generation function."""
    try:
        print("@startuml shared_types")
        print("title Shared Types - RAG TREC 2025")
        print("")

        # Automatically discover all models and enums
        models, enums = discover_models_and_enums()

        # Generate enum definitions first in a grouped box
        generate_enum_definitions(enums)

        # Generate class definitions
        generate_model_definitions(models)

        # Add dynamically discovered relationships
        relationships = extract_relationships(models)
        print("' Dynamic Relationships")
        for rel in sorted(relationships):
            print(rel)

        # Add conceptual/reference relationships that don't exist as direct field references
        print("")
        print("' Reference Relationships")
        print("DatasetSpec --> IndexTarget : indexes built from")
        print("ChunkingSpec --> IndexTarget : indexes built from")
        print("TrecRunRow --> RetrievedSegment : materialises from")

        print("@enduml")

    except Exception as e:
        print(f"Error generating UML: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    generate_uml()
