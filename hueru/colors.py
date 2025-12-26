def rgb_to_xy(r, g, b):
    """Converts RGB color to XY color space for Philips Hue.

    This is a standard conversion formula that includes gamma correction.
    """
    # Normalize RGB values to 0-1 range
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    # Apply gamma correction
    r_final = pow(r_norm, 2.2) if r_norm > 0.04045 else r_norm / 12.92
    g_final = pow(g_norm, 2.2) if g_norm > 0.04045 else g_norm / 12.92
    b_final = pow(b_norm, 2.2) if b_norm > 0.04045 else b_norm / 12.92

    # Convert to XYZ color space
    X = r_final * 0.649926 + g_final * 0.103455 + b_final * 0.197109
    Y = r_final * 0.234327 + g_final * 0.743075 + b_final * 0.022598
    Z = r_final * 0.000000 + g_final * 0.053077 + b_final * 1.035763

    # Convert to xy color space
    if (X + Y + Z) == 0:
        return 0.0, 0.0

    x = X / (X + Y + Z)
    y = Y / (X + Y + Z)

    return x, y