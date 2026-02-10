#!/usr/bin/env python3
"""
Interstellar Donut - A rotating ASCII donut with gravitational lensing

This script renders a rotating torus (donut) in the terminal using ASCII characters,
with gravitational lensing effects simulating light bending around a black hole
according to general relativity.

The physics simulation includes:
- 3D rotation of a torus
- Ray tracing for light paths
- Gravitational lensing (light deflection near massive objects)
- ASCII rendering with proper luminosity-based shading
"""

import math
import time
import sys
import os


class InterstellarDonut:
    """A rotating ASCII donut with gravitational lensing effects."""
    
    def __init__(self, width=80, height=24):
        """
        Initialize the donut renderer.
        
        Args:
            width: Terminal width in characters
            height: Terminal height in characters
        """
        self.width = width
        self.height = height
        
        # Torus parameters
        self.R1 = 1.0  # Inner radius (distance from torus center to tube center)
        self.R2 = 2.0  # Outer radius (tube radius)
        self.K2 = 5.0  # Distance from viewer to screen
        
        # Black hole parameters (for gravitational lensing)
        self.black_hole_mass = 1.0  # Relative mass of the black hole
        self.schwarzschild_radius = 0.5  # Schwarzschild radius (event horizon)
        
        # Rotation angles
        self.A = 0.0  # Rotation around X-axis
        self.B = 0.0  # Rotation around Z-axis
        
        # ASCII luminance characters (from darkest to brightest)
        self.luminance_chars = ".,-~:;=!*#$@"
        
    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def apply_gravitational_lensing(self, x, y, z):
        """
        Apply gravitational lensing effect to light rays.
        
        This simulates how light bends near a massive object (black hole)
        according to general relativity.
        
        Args:
            x, y, z: 3D coordinates of the point
            
        Returns:
            Tuple of (deflection_x, deflection_y, deflection_z) representing
            the bending of light
        """
        # Distance from the black hole center (at origin)
        distance = math.sqrt(x*x + y*y + z*z)
        
        # Avoid division by zero
        if distance < 0.01:
            return (0, 0, 0)
        
        # Calculate deflection angle based on Schwarzschild metric
        # The deflection is proportional to mass/distance
        # and follows the general relativity formula for light bending
        if distance > self.schwarzschild_radius:
            # Deflection factor (simplified GR approximation)
            deflection_factor = (2 * self.black_hole_mass * self.schwarzschild_radius) / (distance * distance)
            
            # Apply deflection in direction towards the black hole center
            deflection_x = -x * deflection_factor
            deflection_y = -y * deflection_factor
            deflection_z = -z * deflection_factor
            
            return (deflection_x, deflection_y, deflection_z)
        else:
            # Inside event horizon - light cannot escape
            return (float('inf'), float('inf'), float('inf'))
    
    def render_frame(self):
        """Render a single frame of the rotating donut."""
        # Create output and depth buffers
        output = [[' ' for _ in range(self.width)] for _ in range(self.height)]
        zbuffer = [[0.0 for _ in range(self.width)] for _ in range(self.height)]
        
        # Precompute sines and cosines for rotation
        cosA = math.cos(self.A)
        sinA = math.sin(self.A)
        cosB = math.cos(self.B)
        sinB = math.sin(self.B)
        
        # Step through the torus
        # theta: angle around the tube
        # phi: angle around the torus center
        theta_spacing = 0.07
        phi_spacing = 0.02
        
        theta = 0.0
        while theta < 2 * math.pi:
            theta += theta_spacing
            
            # Precompute for this theta
            costheta = math.cos(theta)
            sintheta = math.sin(theta)
            
            phi = 0.0
            while phi < 2 * math.pi:
                phi += phi_spacing
                
                # Precompute for this phi
                cosphi = math.cos(phi)
                sinphi = math.sin(phi)
                
                # Calculate 3D coordinates of point on torus surface (before rotation)
                # Circle center distance from origin
                circlex = self.R2 + self.R1 * costheta
                circley = self.R1 * sintheta
                
                # 3D coordinates on torus
                x = circlex * (cosB * cosphi + sinA * sinB * sinphi) - circley * cosA * sinB
                y = circlex * (sinB * cosphi - sinA * cosB * sinphi) + circley * cosA * cosB
                z = self.K2 + cosA * circlex * sinphi + circley * sinA
                ooz = 1.0 / z  # one over z (for perspective projection)
                
                # Apply gravitational lensing
                deflection_x, deflection_y, deflection_z = self.apply_gravitational_lensing(x, y, z - self.K2)
                
                # Check if light is captured by black hole
                if math.isinf(deflection_x):
                    continue
                    
                # Apply deflection to the light path
                x += deflection_x
                y += deflection_y
                z += deflection_z
                ooz = 1.0 / z if abs(z) > 0.01 else 0
                
                # Project to 2D screen coordinates
                xp = int(self.width / 2 + self.width / 3 * ooz * x)
                yp = int(self.height / 2 - self.height / 3 * ooz * y)
                
                # Check if point is within screen bounds
                if 0 <= xp < self.width and 0 <= yp < self.height:
                    # Calculate luminance (surface normal dot product with light direction)
                    # Normal vector to torus surface
                    N_x = costheta * (cosB * cosphi + sinA * sinB * sinphi)
                    N_y = costheta * (sinB * cosphi - sinA * cosB * sinphi)
                    N_z = cosA * costheta * sinphi
                    
                    # Light direction (from upper left)
                    L_x = 0.0
                    L_y = 1.0
                    L_z = -1.0
                    
                    # Normalize light direction
                    L_length = math.sqrt(L_x*L_x + L_y*L_y + L_z*L_z)
                    L_x /= L_length
                    L_y /= L_length
                    L_z /= L_length
                    
                    # Calculate luminance
                    luminance = N_x * L_x + N_y * L_y + N_z * L_z
                    
                    # Add gravitational lensing effect on luminance
                    # Light near the black hole appears dimmer due to redshift
                    distance_to_bh = math.sqrt(x*x + y*y + (z - self.K2)*(z - self.K2))
                    if distance_to_bh > self.schwarzschild_radius:
                        gravitational_redshift = 1.0 - self.schwarzschild_radius / distance_to_bh
                        luminance *= gravitational_redshift
                    
                    # Only render if facing towards viewer and closer than previous points
                    if luminance > 0 and ooz > zbuffer[yp][xp]:
                        zbuffer[yp][xp] = ooz
                        luminance_index = int(luminance * (len(self.luminance_chars) - 1))
                        luminance_index = max(0, min(luminance_index, len(self.luminance_chars) - 1))
                        output[yp][xp] = self.luminance_chars[luminance_index]
        
        # Render the accretion disk glow around the center
        # This creates the characteristic "interstellar" look
        center_x = self.width // 2
        center_y = self.height // 2
        
        for y in range(self.height):
            for x in range(self.width):
                if output[y][x] == ' ':
                    # Calculate distance from center
                    dx = x - center_x
                    dy = (y - center_y) * 2  # Correct for aspect ratio
                    distance = math.sqrt(dx*dx + dy*dy)
                    
                    # Create a dim glow in the center (representing photon sphere)
                    if 3 < distance < 8:
                        glow_intensity = 1.0 - abs(distance - 5.5) / 4.5
                        if glow_intensity > 0.2:
                            glow_index = int(glow_intensity * 3)
                            if glow_index < len(self.luminance_chars):
                                output[y][x] = self.luminance_chars[glow_index]
        
        # Print the frame
        print('\x1b[H', end='')  # Move cursor to home position
        for row in output:
            print(''.join(row))
    
    def run(self, duration=None):
        """
        Run the animation.
        
        Args:
            duration: How many seconds to run (None for infinite)
        """
        self.clear_screen()
        print('\x1b[2J', end='')  # Clear screen
        print('\x1b[?25l', end='')  # Hide cursor
        
        start_time = time.time()
        
        try:
            while True:
                self.render_frame()
                
                # Update rotation angles
                self.A += 0.04
                self.B += 0.02
                
                # Small delay for animation
                time.sleep(0.03)
                
                # Check if duration exceeded
                if duration is not None and time.time() - start_time > duration:
                    break
                    
        except KeyboardInterrupt:
            pass
        finally:
            print('\x1b[?25h', end='')  # Show cursor
            print()


def main():
    """Main entry point for the script."""
    # Get terminal size
    try:
        terminal_size = os.get_terminal_size()
        width = terminal_size.columns
        height = terminal_size.lines - 1  # Leave room for prompt
    except OSError:
        width = 80
        height = 24
    
    # Create and run the donut
    donut = InterstellarDonut(width=width, height=height)
    
    print("Interstellar Donut - Press Ctrl+C to exit")
    time.sleep(2)
    
    donut.run()


if __name__ == "__main__":
    main()
