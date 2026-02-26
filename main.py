import memprocfs # https://github.com/ufrisk/MemProcFS/wiki/API_Python
import win32api
import json
import struct

from calculations import worldToScreen
from overlay import Overlay

# Load offsets
with open("offsets.json", "r") as file: # https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json
    offsets = json.load(file)

clientDll = offsets["client.dll"]
engine2Dll = offsets["engine2.dll"]

entityListOffsets = clientDll["dwEntityList"]
viewmatrixOffsets = clientDll["dwViewMatrix"]
windowHeightOffsets = engine2Dll["dwWindowHeight"]
windowWidthOffsets = engine2Dll["dwWindowWidth"]
localPlayerControllerOffset = clientDll["dwLocalPlayerController"]

# Initialize MemProcFS with FPGA/DMA device
vmm = memprocfs.Vmm(["-device", "fpga"])
proc = vmm.process("cs2.exe")

# Get module bases
clientModule = proc.module("client.dll")
engine2Module = proc.module("engine2.dll")

# Calculate base addresses
entityListBase = clientModule.base + entityListOffsets
viewmatrixBase = clientModule.base + viewmatrixOffsets
windowHeightBase = engine2Module.base + windowHeightOffsets
windowWidthBase = engine2Module.base + windowWidthOffsets
localPlayerControllerBase = clientModule.base + localPlayerControllerOffset

# Read window dimensions (read as 4-byte unsigned integers)
windowHeightBytes = proc.memory.read(windowHeightBase, 4)
windowWidthBytes = proc.memory.read(windowWidthBase, 4)
windowHeight = struct.unpack("<I", windowHeightBytes)[0]
windowWidth = struct.unpack("<I", windowWidthBytes)[0]
SCREEN_SIZE = (windowHeight, windowWidth)

print(f"Screen size: {windowWidth}x{windowHeight}")

# Get local player info for team comparison
localTeam = 0
localPlayerPawn = 0

try:
    # Read local player controller
    localControllerBytes = proc.memory.read(localPlayerControllerBase, 8)
    localPlayerController = struct.unpack("<Q", localControllerBytes)[0]
    
    if localPlayerController:
        # Read team from controller - m_iTeamNum offset
        # In CCSPlayerController, team is typically at 0x3C or 0x40
        teamBytes = proc.memory.read(localPlayerController + 0x3C, 4)
        localTeam = struct.unpack("<i", teamBytes)[0]
        print(f"Local team: {localTeam}")
        
        # Get local player pawn for additional checks
        # m_hPawn in CCSPlayerController
        pawnHandleBytes = proc.memory.read(localPlayerController + 0x60C, 8)
        localPlayerPawn = struct.unpack("<Q", pawnHandleBytes)[0] & 0xFFFFFFFF
        
except Exception as e:
    print(f"Error reading local player: {e}")

# Initialize overlay
overlay = Overlay(SCREEN_SIZE)

# Entity structure offsets (these need verification from client.dll.json)
# Common CS2 entity offsets:
OFFSET_HEALTH = 0xD0           # m_iHealth
OFFSET_TEAM = 0x3C             # m_iTeamNum  
OFFSET_DORMANT = 0xEF          # m_bDormant (may vary)
OFFSET_POSITION = 0x308        # m_vOldOrigin or m_vecOrigin (VERIFY THIS!)
OFFSET_PAWN_HANDLE = 0x60C     # m_hPawn in controller

def get_entity_pawn(controller_ptr):
    """Get player pawn from controller"""
    try:
        handle_bytes = proc.memory.read(controller_ptr + OFFSET_PAWN_HANDLE, 8)
        handle = struct.unpack("<Q", handle_bytes)[0]
        # Handle is lower 32 bits for entity index
        entity_index = handle & 0xFFFFFFFF
        if entity_index == 0xFFFFFFFF:
            return 0
        return entity_index
    except:
        return 0

# Main loop
frame_count = 0
while True:
    if not overlay.refresh():
        break
    
    entities = []
    
    # Read view matrix (16 floats = 64 bytes)
    try:
        rawData = proc.memory.read(viewmatrixBase, 64)
        viewmatrix = struct.unpack("<16f", rawData)
    except Exception as e:
        print(f"Error reading viewmatrix: {e}")
        continue
    
    # Iterate entity list
    for i in range(64):
        try:
            # CS2 Entity List Structure:
            # entityList = [[EntityPtr, EntityPtr, ...], [EntityPtr, ...], ...]
            # Each chunk has 512 entities (0x20 * 512 = 0x4000)
            
            # Calculate chunk and index within chunk
            chunk_index = i // 512
            entity_index = i % 512
            
            # Read chunk pointer
            chunk_ptr_addr = entityListBase + (chunk_index * 0x8)
            chunk_ptr_bytes = proc.memory.read(chunk_ptr_addr, 8)
            chunk_ptr = struct.unpack("<Q", chunk_ptr_bytes)[0]
            
            if not chunk_ptr or chunk_ptr == 0:
                continue
            
            # Read entity pointer from chunk
            entity_ptr_addr = chunk_ptr + (entity_index * 0x20)
            entityPtrBytes = proc.memory.read(entity_ptr_addr, 8)
            
            if not entityPtrBytes:
                continue
            
            entityPointer = struct.unpack("<Q", entityPtrBytes)[0]
            if not entityPointer or entityPointer == 0:
                continue
            
            # Skip if this is local player
            if entityPointer == localPlayerPawn:
                continue
            
            # Read health (4 bytes signed int)
            healthBytes = proc.memory.read(entityPointer + OFFSET_HEALTH, 4)
            health = struct.unpack("<i", healthBytes)[0]
            
            if health <= 0 or health > 100:
                continue
            
            # Check dormancy - skip if dormant
            try:
                dormantBytes = proc.memory.read(entityPointer + OFFSET_DORMANT, 1)
                isDormant = struct.unpack("<B", dormantBytes)[0]
                if isDormant:
                    continue
            except:
                pass  # If dormancy read fails, continue anyway
            
            # Check team - skip teammates
            teamBytes = proc.memory.read(entityPointer + OFFSET_TEAM, 4)
            team = struct.unpack("<i", teamBytes)[0]
            if team == localTeam or team == 0:
                continue
            
            # Read position - m_vOldOrigin or m_vecOrigin
            # NOTE: Verify OFFSET_POSITION (0x308) against client.dll.json!
            posBytes = proc.memory.read(entityPointer + OFFSET_POSITION, 12)  # 3 floats
            feet_x, feet_y, feet_z = struct.unpack("<3f", posBytes)
            
            # Artificial head position (add 64 units to Z)
            head_z = feet_z + 64.0
            
            # Convert to screen coordinates
            feetPos = (feet_x, feet_y, feet_z)
            headPos = (feet_x, feet_y, head_z)
            
            feetCoords = worldToScreen(viewmatrix, feetPos, SCREEN_SIZE)
            headCoords = worldToScreen(viewmatrix, headPos, SCREEN_SIZE)
            
            # Skip if behind camera or off-screen
            if feetCoords == (0, 0) or headCoords == (0, 0):
                continue
            
            # Calculate box dimensions
            height = feetCoords[1] - headCoords[1]
            if height < 0:
                continue  # Skip if inverted
            
            width = height / 2.5
            
            # Color based on health (green -> yellow -> red)
            if health > 75:
                color = win32api.RGB(0, 255, 0)  # Green
            elif health > 40:
                color = win32api.RGB(255, 255, 0)  # Yellow
            else:
                color = win32api.RGB(255, 0, 0)  # Red
            
            entities.append({
                "x": headCoords[0] - width / 2,
                "y": headCoords[1],
                "w": width,
                "h": height,
                "color": color,
                "health": health
            })
            
        except Exception as e:
            # Silently continue on errors
            continue
    
    # Draw all entities
    for ent in entities:
        overlay.draw_box(ent["x"], ent["y"], ent["w"], ent["h"], ent["color"])
        overlay.draw_health_bar(ent["x"], ent["y"], ent["w"], ent["health"])
    
    overlay.display(fps=60)
    frame_count += 1
