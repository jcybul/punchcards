# app/services/strip_generator.py
"""
Generate dynamic strip images by overlaying mug assets.
"""
from PIL import Image
from pathlib import Path
import io
import os
from app.services.asset_service import get_program_icon
import math 

ASSETS = Path(os.getenv("WALLET_ASSETS_DIR", "/Users/josephcybulzebede/Documents/punchcards/assets"))

def hex_to_rgb(hex_color: str) -> tuple:
    """Convert #RRGGBB to (R, G, B) tuple."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b) 


def calculate_layout(punches_required: int):
    """
    Calculate optimal layout for given number of punches.
    Returns: (rows, items_per_row_list)
    
    Examples:
    - 8 punches → 2 rows, [4, 4]
    - 10 punches → 2 rows, [5, 5]
    - 7 punches → 2 rows, [4, 3]
    - 12 punches → 2 rows, [6, 6]
    """
    if punches_required <= 5:
        # Single row
        return 1, [punches_required]
    
    elif punches_required <= 10:
        # Two rows, balanced
        rows = 2
        items_per_row = punches_required / 2
        
        if punches_required % 2 == 0:
            # Even split: 8 → [4, 4], 10 → [5, 5]
            return rows, [int(items_per_row), int(items_per_row)]
        else:
            # Odd: top row gets one more: 7 → [4, 3], 9 → [5, 4]
            return rows, [math.ceil(items_per_row), math.floor(items_per_row)]
    
    elif punches_required <= 15:
        # Three rows, balanced
        rows = 3
        base_items = punches_required // 3
        extra = punches_required % 3
        
        # Distribute extras to first rows
        if extra == 0:
            return rows, [base_items, base_items, base_items]
        elif extra == 1:
            return rows, [base_items + 1, base_items, base_items]
        else:  # extra == 2
            return rows, [base_items + 1, base_items + 1, base_items]
    
    else:
        # Four rows for 16+
        rows = 4
        base_items = punches_required // 4
        extra = punches_required % 4
        
        layout = [base_items] * 4
        for i in range(extra):
            layout[i] += 1
        
        return rows, layout


def generate_strip_with_punches(
    punches: int, 
    punches_required: int, 
    reward_credits: int,
    strip_color: str,
    filled_icon_url: str | None,
    empty_icon_url: str | None
) -> bytes:
    """
    Generate a strip image with dynamic balanced layout.
    """
    # Parse color
    rgb = hex_to_rgb(strip_color)
    
    # Create background
    img = Image.new("RGBA", (750, 246), (*rgb, 255))
    
    # Get icons
    filled_icon = get_program_icon(filled_icon_url, "filled")
    empty_icon = get_program_icon(empty_icon_url, "empty")
    
    if not filled_icon or not empty_icon:
        # Return plain strip if icons fail
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    
    # Load as PIL images
    mug_filled = Image.open(io.BytesIO(filled_icon)).convert("RGBA")
    mug_empty = Image.open(io.BytesIO(empty_icon)).convert("RGBA")
    
    # Get original size
    mug_width = mug_filled.width
    mug_height = mug_filled.height
    
    # Calculate layout
    num_rows, items_per_row = calculate_layout(punches_required)
    
    # Calculate vertical spacing
    strip_height = 250
    vertical_margin = 70
    available_height = strip_height - (2 * vertical_margin)
    
    if num_rows == 1:
        row_positions = [strip_height // 2]
    else:
        row_spacing = available_height / (num_rows - 1)
        row_positions = [int(vertical_margin + (i * row_spacing)) for i in range(num_rows)]
    
    # Place mugs
    icon_index = 0
    
    for row_num in range(num_rows):
        items_in_row = items_per_row[row_num]
        y_position = row_positions[row_num]
        
        content_width = 600  
        strip_width = 750 
        horizontal_margin = 40  
        
        content_offset = (strip_width - content_width) // 2
        
        available_width = content_width - (2 * horizontal_margin)
        
        
        if items_in_row == 1:
            x_positions = [content_offset + (content_width // 2)]
        else:
            x_spacing = available_width / (items_in_row - 1)
            x_positions = [
                int(content_offset + horizontal_margin + (i * x_spacing)) 
                for i in range(items_in_row)
            ]
        
        # Place icons in this row
        for col_num in range(items_in_row):
            x_position = x_positions[col_num]
            
            # Choose filled or empty
            icon = mug_filled if icon_index < punches else mug_empty
            
            # Center icon on position
            paste_x = x_position - (mug_width // 2)
            paste_y = y_position - (mug_height // 2)
            
            img.paste(icon, (paste_x, paste_y), icon)
            
            icon_index += 1

    
    # Convert to bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()