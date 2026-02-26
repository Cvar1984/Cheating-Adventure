import win32gui
import win32con
import win32api
import win32ui

class Overlay:
    def __init__(self, screen_size):
        self.screen_size = screen_size
        self.height, self.width = screen_size
        
        # Get target window (CS2)
        self.hwnd = win32gui.FindWindow(None, "Counter-Strike 2")
        if not self.hwnd:
            # Try alternative names
            self.hwnd = win32gui.FindWindow("SDL_app", None)
        
        if not self.hwnd:
            raise Exception("CS2 window not found")
        
        # Create overlay window
        self.overlay_hwnd = win32gui.CreateWindowEx(
            win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST,
            "STATIC",
            None,
            win32con.WS_POPUP,
            0, 0, self.width, self.height,
            None, None, None, None
        )
        
        # Get window DC
        self.hdc = win32gui.GetDC(self.overlay_hwnd)
        self.mem_dc = win32gui.CreateCompatibleDC(self.hdc)
        
        # Create bitmap
        self.bitmap = win32gui.CreateCompatibleBitmap(self.hdc, self.width, self.height)
        win32gui.SelectObject(self.mem_dc, self.bitmap)
        
        # Create pen and brush for drawing
        self.pen = win32gui.CreatePen(win32con.PS_SOLID, 1, win32api.RGB(255, 0, 0))
        self.brush = win32gui.CreateSolidBrush(win32api.RGB(0, 0, 0))
        
        # Store draw commands for frame
        self.draw_commands = []
    
    def refresh(self):
        """Check if overlay should continue running"""
        # Check if CS2 is still running
        if not win32gui.IsWindow(self.hwnd):
            return False
        
        # Update overlay position to match CS2 window
        rect = win32gui.GetWindowRect(self.hwnd)
        x, y, right, bottom = rect
        width = right - x
        height = bottom - y
        
        win32gui.SetWindowPos(
            self.overlay_hwnd,
            win32con.HWND_TOPMOST,
            x, y, width, height,
            win32con.SWP_NOACTIVATE
        )
        
        # Clear draw commands
        self.draw_commands = []
        
        return True
    
    def draw_box(self, x, y, width, height, color):
        """Queue a box to be drawn"""
        self.draw_commands.append(('box', x, y, width, height, color))
    
    def draw_health_bar(self, x, y, width, health):
        """Queue a health bar to be drawn"""
        self.draw_commands.append(('health', x, y, width, health))
    
    def display(self, fps=60):
        """Render all queued draw commands"""
        # Clear bitmap
        win32gui.PatBlt(self.mem_dc, 0, 0, self.width, self.height, win32con.WHITENESS)
        
        # Execute draw commands
        for cmd in self.draw_commands:
            if cmd[0] == 'box':
                _, x, y, w, h, color = cmd
                # Create pen with specific color
                pen = win32gui.CreatePen(win32con.PS_SOLID, 2, color)
                old_pen = win32gui.SelectObject(self.mem_dc, pen)
                
                # Draw rectangle
                win32gui.Rectangle(self.mem_dc, int(x), int(y), int(x + w), int(y + h))
                
                # Cleanup
                win32gui.SelectObject(self.mem_dc, old_pen)
                win32gui.DeleteObject(pen)
                
            elif cmd[0] == 'health':
                _, x, y, w, health = cmd
                # Draw health bar above box
                bar_width = w
                bar_height = 4
                health_pct = max(0, min(100, health)) / 100.0
                
                # Background (red)
                bg_brush = win32gui.CreateSolidBrush(win32api.RGB(255, 0, 0))
                old_brush = win32gui.SelectObject(self.mem_dc, bg_brush)
                win32gui.Rectangle(self.mem_dc, int(x), int(y - 8), int(x + bar_width), int(y - 8 + bar_height))
                win32gui.SelectObject(self.mem_dc, old_brush)
                win32gui.DeleteObject(bg_brush)
                
                # Health (green)
                health_width = int(bar_width * health_pct)
                if health_width > 0:
                    health_brush = win32gui.CreateSolidBrush(win32api.RGB(0, 255, 0))
                    old_brush = win32gui.SelectObject(self.mem_dc, health_brush)
                    win32gui.Rectangle(self.mem_dc, int(x), int(y - 8), int(x + health_width), int(y - 8 + bar_height))
                    win32gui.SelectObject(self.mem_dc, old_brush)
                    win32gui.DeleteObject(health_brush)
        
        # Update layered window
        point_src = win32gui.GetWindowRect(self.overlay_hwnd)
        size = (point_src[2] - point_src[0], point_src[3] - point_src[1])
        
        if size[0] > 0 and size[1] > 0:
            # Use UpdateLayeredWindow for transparency
            from ctypes import windll, c_void_p, c_int, pointer, sizeof, Structure, c_ulong
            
            hdc_screen = win32gui.GetDC(0)
            
            # Blend function
            blend = 255  # Full opacity for drawn content
            
            # This is a simplified version - full implementation would use ctypes for UpdateLayeredWindow
            win32gui.BitBlt(hdc_screen, point_src[0], point_src[1], size[0], size[1], self.mem_dc, 0, 0, win32con.SRCCOPY)
            win32gui.ReleaseDC(0, hdc_screen)
        
        # Frame rate limiting
        import time
        time.sleep(1.0 / fps)
    
    def cleanup(self):
        """Clean up resources"""
        win32gui.DeleteObject(self.bitmap)
        win32gui.DeleteDC(self.mem_dc)
        win32gui.ReleaseDC(self.overlay_hwnd, self.hdc)
        win32gui.DestroyWindow(self.overlay_hwnd)


# Standalone test
if __name__ == "__main__":
    # Test overlay creation
    overlay = Overlay((1080, 1920))
    print("Overlay created successfully")
    overlay.cleanup()
