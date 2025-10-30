# app/services/strip_generator.py
"""
Generate dynamic strip images by overlaying mug assets.
"""
from PIL import Image
from pathlib import Path
import io
import os
from app.services.asset_service import get_program_icon

ASSETS = Path(os.getenv("WALLET_ASSETS_DIR", "/Users/josephcybulzebede/Documents/punchcards/assets"))

def hex_to_rgb(hex_color: str) -> str:
    """Convert #RRGGBB to R,G,B format for Apple Wallet."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"{r},{g},{b}"


def generate_strip_with_punches(
    punches: int, 
    punches_required: int, 
    reward_credits: int,
    strip_color: str,
    filled_icon_url: str | None,
    empty_icon_url: str | None
) -> bytes:
    """
    Generate a strip image by overlaying designer-created mug assets.
    Two rows of 5 mugs each.
    """
    
    strip_color_rgb = hex_to_rgb(strip_color)
    r, g, b = map(int, strip_color_rgb.split(','))
    
    img = Image.new("RGBA", (750, 246), (r, g, b, 255))
    
    filled_icon = get_program_icon(filled_icon_url, "filled")
    empty_icon = get_program_icon(empty_icon_url, "empty")
    
    if not filled_icon or not empty_icon:
        # Return plain strip if icons fail
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    
    # Load as PIL images
    from io import BytesIO
    mug_filled = Image.open(BytesIO(filled_icon)).convert("RGBA")
    mug_empty = Image.open(BytesIO(empty_icon)).convert("RGBA")
    
    mug_width = mug_filled.width
    mug_height = mug_filled.height
    
    # Two rows of 5 mugs each
    mugs_per_row = 5
    
    # Horizontal spacing
    margin = 110
    available_width = 750 - (2 * margin)
    x_spacing = available_width / (mugs_per_row - 1)
    
    # Vertical positions for two rows
    row_1_y = 60  # Top row
    row_2_y = 150  # Bottom row
    
    # Place mugs in grid
    for i in range(punches_required):
        # Determine row and column
        row = i // mugs_per_row  # 0 for first row, 1 for second row
        col = i % mugs_per_row   # 0-4 position in row
        
        # Calculate position
        x_position = int(margin + (col * x_spacing) - (mug_width // 2))
        y_position = row_1_y if row == 0 else row_2_y
        
        # Choose filled or empty mug
        if i < punches:
            img.paste(mug_filled, (x_position, y_position), mug_filled)
        else:
            img.paste(mug_empty, (x_position, y_position), mug_empty)
    
    # Convert to bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
