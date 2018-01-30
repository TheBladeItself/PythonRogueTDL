import tdl
from random import randint
import tcod.color as colours
import math
import textwrap
from tcod import image_load

# Actual size of window
SCREEN_WIDTH		= 80
SCREEN_HEIGHT		= 50

# Size of the map
MAP_WIDTH			= 80
MAP_HEIGHT			= 43

# GUI sizes and co-ordinates
BAR_WIDTH			= 20
PANEL_HEIGHT		= 7
PANEL_Y				= SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X				= BAR_WIDTH + 2
MSG_WIDTH			= SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT			= PANEL_HEIGHT - 1
INVENTORY_WIDTH		= 50

# Parameters for dungeon Generation
ROOM_MAX_SIZE		= 10
ROOM_MIN_SIZE		= 6
MAX_ROOMS			= 30
MAX_ROOM_MONSTERS	= 3
MAX_ROOM_ITEMS		= 2

FOV_ALGO			= 'BASIC'	# default FOV algorithm
FOV_LIGHT_WALLS		= True
TORCH_RADIUS		= 10

# Spell Values
HEAL_AMOUNT			= 4
LIGHTNING_RANGE		= 5
LIGHTNING_DAMAGE	= 20
CONFUSE_RANGE		= 8
CONFUSE_NUM_TURNS	= 10
FIREBALL_RADIUS     = 3

CLASSIC_TILES		= False		# Classic Tiles is not fully implemented yet

col_dark_wall		= (0, 0, 100)
col_ligt_wall		= (130, 110, 50)
col_dark_grnd		= (50, 50, 150)
col_ligt_grnd		= (200, 180, 50)

class Tile():
	# Map Tile & its properties
	def __init__(self, blocked, block_sight=None):
		self.blocked = blocked
		
		# Default: If a tile is blocked, it also blocks sight
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight
		
		self.explored = False

class Rect():
	# Map Rectangle - used to represent rooms
	def __init__(self, x, y, w, h):
		self.x1 = x
		self.y1 = y
		self.x2 = x + w
		self.y2 = y + h
		
	def centre(self):
		centre_x = (self.x1 + self.x2) // 2
		centre_y = (self.y1 + self.y2) // 2
		return (centre_x, centre_y)
		
	def intersect(self, other):
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and
			self.y1 <= other.y2 and self.y2 >= other.y1)

class GameObject:
	# This represents a generic object - it's always represented by a
	# character on screen
	def __init__(self, x, y, char, name, colour, blocks=False, fighter=None, ai=None, item=None):
		self.x = x
		self.y = y
		self.char = char
		self.name = name
		self.colour = colour
		self.blocks = blocks
		
		self.fighter = fighter
		if self.fighter: self.fighter.owner = self
		
		self.ai = ai
		if self.ai: self.ai.owner = self
		
		self.item = item
		if self.item: self.item.owner = self
		
	def move(self, dx, dy):
		# Move by the amount given
		if not is_blocked(self.x + dx, self.y + dy):
			self.x += dx
			self.y += dy
	
	def draw(self):
		global visible_tiles
		# draws the character at its position, if visible
		if (self.x, self.y) in visible_tiles:
			if CLASSIC_TILES:con.draw_char(self.x, self.y, self.char, self.colour)
			else: con.draw_char(self.x, self.y, self.char, self.colour, bg=col_ligt_grnd)
	
	def clear(self):
		# erases the character
		con.draw_char(self.x, self.y, ' ', self.colour, bg=None)
		
	def move_towards(self, target_x, target_y):
		# Vector from this object to the target, and distance
		dx = target_x - self.x
		dy = target_y - self.y
		distance = math.sqrt(dx ** 2 + dy ** 2)
		
		# Normalise it to length 1 (preserving direction)
		# Round it and convert it to an integer
		dx = int(round(dx/distance))
		dy = int(round(dy/distance))
		self.move(dx,dy)
	
	def distance_to(self, other):
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)
		
	def distance(self, x, y):
		return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)
		
	def send_to_back(self):
		global objects
		objects.remove(self)
		objects.insert(0, self)

class Fighter:
	def __init__(self, hp, defense, power, death_function=None):
		self.max_hp = hp
		self.hp = hp
		self.defense = defense
		self.power = power
		self.death_function = death_function
		
	def take_damage(self, damage):
		if damage > 0:
			self.hp -= damage
		if self.hp <= 0:
			function = self.death_function
			if function is not None: function(self.owner)
		
	def attack(self, target):
		# VERY SIMPLE PLACEHOLDER FORMULA FOR ATTACKS
		damage = self.power - target.fighter.defense
		
		if damage > 0:
			print(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
			target.fighter.take_damage(damage)
		else:
			print(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!') 
	
	def heal(self, amount):
		self.hp += amount
		if self.hp > self.max_hp: self.hp = self.max_hp
	
class Item:
	def __init__(self, use_function=None):
		self.use_function = use_function
	
	def pick_up(self):
		if len(inventory) >= 26:
			message('Your inventory is full, cannot pick up ' + self.owner.name + '.', colours.red)
		else:
			inventory.append(self.owner)
			objects.remove(self.owner)
			message('You picked up a ' + self.owner.name + '!', colours.green)
		
	def drop(self):
		objects.append(self.owner)
		inventory.remove(self.owner)
		self.owner.x = player.x
		self.owner.y = player.y
		message('You dropped a ' + self.owner.name + '.', colours.yellow)
			
	def use(self):
		if self.use_function is None:
			message('The ' + self.owner.name + ' cannot be used')
		else:
			if self.use_function() != 'cancelled':
				inventory.remove(self.owner)	# Destroy after use, unless cancelled
		
class BasicMonster:
	def take_turn(self):
		monster = self.owner
		if(monster.x, monster.y) in visible_tiles:
			# Move towards player if far away
			if monster.distance_to(player) >= 2:
				monster.move_towards(player.x, player.y)
			
			# Attack!
			elif player.fighter.hp > 0: monster.fighter.attack(player)

class ConfusedMonster:
	def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
		self.old_ai = old_ai
		self.num_turns = num_turns
	
	def take_turn(self):
		if self.num_turns > 0:
			# Move Randomly
			self.owner.move(randint(-1, 1), randint(-1, 1))
			self.num_turns -= 1
		else: # Restore old AI
			self.owner.ai = self.oldai
			message('The ' + self.owner.name + ' is no longer confused!', colours.red)

def is_blocked(x, y):
	# Test the map tile
	if my_map[x][y].blocked: return True
	
	# Check for blocking objects
	for obj in objects:
		if obj.blocks and obj.x == x and obj.y == y:
			return True
	return False

def create_room(room):
	global my_map
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			my_map[x][y].blocked = False
			my_map[x][y].block_sight = False

def create_h_tunnel(x1, x2, y):
	global my_map
	for x in range(min(x1, x2), max(x1, x2) + 1):
		my_map[x][y].blocked = False
		my_map[x][y].block_sight = False

def create_v_tunnel(y1, y2, x):
	global my_map
	for y in range(min(y1, y2), max(y1, y2) + 1):
		my_map[x][y].blocked = False
		my_map[x][y].block_sight = False

def is_visible_tile(x, y):
	global my_map
 
	if x >= MAP_WIDTH or x < 0:
		return False
	elif y >= MAP_HEIGHT or y < 0:
		return False
	elif my_map[x][y].blocked == True:
		return False
	elif my_map[x][y].block_sight == True:
		return False
	else:
		return True

def make_map():
	global my_map, objects
	
	objects = [player]
	
	# fill map with 'blocked' tiles
	my_map = [[ Tile(True)	for y in range(MAP_HEIGHT)] for x in range(MAP_WIDTH)]
	
	rooms = []
	num_rooms = 0
	
	for r in range(MAX_ROOMS):
		# Randomise width and height
		w = randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		h = randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		# Randomise position
		x = randint(0, MAP_WIDTH - w - 1)
		y = randint(0, MAP_HEIGHT - h - 1)
		
		# Rect class
		new_room = Rect(x, y, w, h)
		
		# Check that there are no intersections
		failed = False
		for other_room in rooms:
			if new_room.intersect(other_room):
				failed = True
				break
		if not failed:
			# Room is valid
			
			create_room(new_room)
			
			(new_x, new_y) = new_room.centre()
			
			if num_rooms == 0:
				player.x = new_x
				player.y = new_y
			else:
				# Connect to previous room
				
				# Centre Co-ordinates of previous room
				(prev_x, prev_y) = rooms[num_rooms-1].centre()
				
				if randint(0, 1):
					create_h_tunnel(prev_x, new_x, prev_y)
					create_v_tunnel(prev_y, new_y, new_x)
				else:
					create_v_tunnel(prev_y, new_y, prev_x)
					create_h_tunnel(prev_x, new_x, new_y)
			
			# Add monsters to room
			place_objects(new_room)
			
			# Append room to the list
			rooms.append(new_room)
			num_rooms += 1

def place_objects(room):
	# Choose random number of monsters
	num_monsters = randint(0, MAX_ROOM_MONSTERS)
	
	for i in range(num_monsters):
		x = randint(room.x1+1, room.x2-1)
		y = randint(room.y1+1, room.y2-1)
		
		if not is_blocked(x, y):
			if randint(0, 100) < 80:
				fighter_component = Fighter(hp=10, defense=0, power=3,
					death_function=monster_death)
				ai_component = BasicMonster()
				monster = GameObject(x, y, 'o', 'orc', colours.desaturated_green,
					blocks=True, fighter=fighter_component, ai=ai_component)		
			else:
				fighter_component = Fighter(hp=16, defense=1, power=4,
					death_function=monster_death)
				ai_component = BasicMonster()
				monster = GameObject(x, y, 'T', 'troll', colours.darker_green,
					blocks=True, fighter=fighter_component, ai=ai_component)		
			
			objects.append(monster)
		
	num_items = randint(0, MAX_ROOM_ITEMS)
	
	for i in range(num_items):
		x = randint(room.x1+1, room.x2-1)
		y = randint(room.y1+1, room.y2-1)
		
		if not is_blocked(x, y):
			dice = randint(0, 100)
			if dice < 70: # Healing Potion
				item_component = Item(use_function=cast_heal)
				item = GameObject(x, y, '!', 'healing potion', colours.violet,
					item=item_component)
			elif dice < 70+10: # Lightning Rune
				item_component = Item(use_function=cast_lightning)
				item = GameObject(x, y, '#', 'lightning rune', colours.light_yellow,
					item=item_component)
			elif dice < 70+10+10: # Fireball Rune
				item_component = Item(use_function=cast_fireball)
				item = GameObject(x, y, '#', 'fireball rune', colours.light_yellow,
					item=item_component)
			else: # Confuse Rune
				item_component = Item(use_function=cast_confuse)
				item = GameObject(x, y, '#', 'confusion rune', colours.light_yellow,
					item=item_component)
				
			objects.append(item)
			item.send_to_back()

def render_all():
	global fov_recompute
	global visible_tiles
	
	if fov_recompute:
		fov_recompute = False
		visible_tiles = tdl.map.quickFOV(player.x, player.y, 
			is_visible_tile, fov=FOV_ALGO, radius=TORCH_RADIUS, 
			lightWalls=FOV_LIGHT_WALLS)
	
	# Set tile background colours
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			visible = (x, y) in visible_tiles
			wall = my_map[x][y].block_sight
			if not visible:
				if my_map[x][y].explored:
					if CLASSIC_TILES:
						if wall: con.draw_char(x, y, '#', fg=col_white, bg=colours.black)
						else: con.draw_char(x, y, '.', fg=col_white, bg=colours.black)
					else:
						if wall: con.draw_char(x, y, ' ', fg=None, bg=col_dark_wall)
						else: con.draw_char(x, y, ' ', fg=None, bg=col_dark_grnd)
			else:
				if CLASSIC_TILES:
					if wall: con.draw_char(x, y, '#', fg=col_white, bg=col_grey)
					else: con.draw_char(x, y, '.', fg=col_white, bg=col_grey)
				else:
					if wall: con.draw_char(x, y, ' ', fg=None, bg=col_ligt_wall)
					else: con.draw_char(x, y, ' ', fg=None, bg=col_ligt_grnd)
				my_map[x][y].explored = True
				
	# Draw objects in list
	for obj in objects: obj.draw()
	player.draw()
	
	root.blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0)
	
	# Prepare to render the GUI panel
	panel.clear(fg=colours.white, bg=colours.black)
	
	# Print Messages
	y = 1
	for (line, colour) in game_msgs:
		panel.draw_str(MSG_X, y, line, bg=None, fg=colour)
		y += 1
	
	# Show the player's stats
	render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
		colours.light_red, colours.darker_red)
	
	#display names of objects under the mouse
	panel.draw_str(1, 0, get_names_under_mouse(), bg=None, fg=colours.light_gray)
	
	root.blit(panel, 0, PANEL_Y, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0)

def player_move_or_attack(dx, dy):
	global fov_recompute

	#the coordinates the player is moving to/attacking
	x = player.x + dx
	y = player.y + dy
 
	#try to find an attackable object there
	target = None
	for obj in objects:
		if obj.fighter and obj.x == x and obj.y == y:
			target = obj
			break
 
	#attack if target found, move otherwise
	if target is not None:
		player.fighter.attack(target)
	else:
		player.move(dx, dy)
		fov_recompute = True	
	
def menu(header, options, width):
	if len(options) > 26:
		raise ValueError('Cannot have a menu with more than 26 options.')
	
	# Calculate the total height for the header (after textwrap) with one line per option
	header_wrapped = []
	for header_line in header.splitlines():
		header_wrapped.extend(textwrap.wrap(header_line, width))
	header_height = len(header_wrapped)
	if header == '': header_height = 0
	height = len(options) + header_height
	
	# Create an off-screen console that represents the menu's window
	window = tdl.Console(width, height)
	
	# Print the header, with wrapped text
	window.draw_rect(0, 0, width, height, None, fg=colours.white, bg=None)
	for i, line in enumerate(header_wrapped):
		window.draw_str(0, 0+i, header_wrapped[i])
	
	# Print all of the Options
	y = header_height
	letter_index = ord('a')
	for option_text in options:
		text = '(' + chr(letter_index) + ') ' + option_text
		window.draw_str(0, y, text, bg=None)
		y += 1
		letter_index += 1
		
	# Blit the contents of "window" to the root console
	x = SCREEN_WIDTH//2 - width//2
	y = SCREEN_HEIGHT//2 - height//2
	root.blit(window, x, y, width, height, 0, 0)
	
	#present the root console to the player and wait for a key-press
	tdl.flush()
	key = tdl.event.key_wait()
	key_char = key.char
	if key_char == '': key_char = ' ' # placeholder
 
    #convert the ASCII code to an index; if it corresponds to an option, return it
	index = ord(key_char) - ord('a')
	if index >= 0 and index < len(options): return index
	return None

def msgbox(text, width=50):
	menu(text, [], width) 
	
def inventory_menu(header):
	if len(inventory) == 0:
		options = ['Your inventory is empty.']
	else:
		options = [item.name for item in inventory]
	index = menu(header, options, INVENTORY_WIDTH)
	
	# If an item was chosen, return it
	if index is None or len(inventory) == 0: return None
	return inventory[index].item
	
def main_menu():
	img = image_load('menu_background.png')
	
	while not tdl.event.is_window_closed():
		img.blit_2x(root, 0, 0)	# Blit the image, at twice the regular console resolution
		
		# Game Title and Credits
		title = 'THE ABYSS'
		centre = (SCREEN_WIDTH - len(title)) // 2
		root.draw_str(centre, SCREEN_HEIGHT // 2 -4, title, bg=None, fg=colours.light_yellow)
		
		title = 'by Edward Powell'
		centre = (SCREEN_WIDTH - len(title)) // 2
		root.draw_str(centre, SCREEN_HEIGHT-2, title, bg=None, fg=colours.light_yellow)
		
		# Show options
		choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)
		
		if choice == 0:
			new_game()
			play_game()
		if choice == 1:  #load last game
			try: load_game()
			except:
				msgbox('\n No saved game to load.\n', 24)
				continue
			play_game()
		elif choice == 2: break
	
def handle_keys():
	global playerx, playery
	global fov_recompute
	global mouse_coord
	
	keypress = False
	for event in tdl.event.get():
		if event.type == 'KEYDOWN':
			user_input = event
			keypress = True
		if event.type == 'MOUSEMOTION':
			mouse_coord = event.cell
	
	if not keypress:
		return 'didnt-take-turn'
	
	if user_input.key == 'ENTER' and user_input.alt:
		# Alt & Enter: toggle fullscreen
		tdl.set_fullscreen(not tdl.get_fullscreen())
	elif user_input.key == 'ESCAPE':
		return 'exit'	# exit game
	
	if game_state == 'playing':
		# Movement Keys
		if user_input.key == 'UP': player_move_or_attack(0, -1)
		elif user_input.key == 'DOWN': player_move_or_attack(0, 1)
		elif user_input.key == 'LEFT': player_move_or_attack(-1, 0)
		elif user_input.key == 'RIGHT':	player_move_or_attack(1, 0)
		else: # test for other keys
			if user_input.text == 'g': # Pick up an item
				for obj in objects:
					if obj.x == player.x and obj.y == player.y and obj.item:
						obj.item.pick_up()
						break 
			if user_input.text == 'i': # Show the Inventory
				chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
				if chosen_item is not None: chosen_item.use()
			if user_input.text == 'd':
				#show the inventory; if an item is selected, drop it
				chosen_item = inventory_menu('Press the key next to an item to' + 
				'drop it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.drop()
			return 'didnt-take-turn'

def player_death(player):
	global game_state
	print('You died!')
	game_state = 'dead'
	
	player.char = '%'
	player.colour = colours.dark_red
	
def monster_death(monster):
	print(monster.name.capitalize() + ' is dead!')
	monster.char = '%'
	monster.colour = colours.dark_red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()

def render_bar(x, y, total_width, name, value, maximum, bar_colour, back_colour):
	bar_width = int(float(value) / maximum * total_width)
	
	panel.draw_rect(x, y, total_width, 1, None, bg=back_colour)
	if bar_width > 0: panel.draw_rect(x, y, bar_width, 1, None, bg=bar_colour)
	
	text = name + ': ' + str(value) + '/' + str(maximum)
	x_centred = x + (total_width-len(text))//2
	panel.draw_str(x_centred, y, text, fg=colours.white, bg=None)

def message(new_msg, colour=colours.white):
	new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)	# Split the text if necessary
	
	for line in new_msg_lines:
		if len(game_msgs) == MSG_HEIGHT: del game_msgs[0]
		
		game_msgs.append((line, colour))

def get_names_under_mouse():
	global visible_tiles

	#return a string with the names of all objects under the mouse
	(x, y) = mouse_coord
 
	#create a list with the names of all objects at the mouse's coordinates and in FOV
	names = [obj.name for obj in objects
		if obj.x == x and obj.y == y and (obj.x, obj.y) in visible_tiles]
 
	names = ', '.join(names)  #join the names, separated by commas
	return names.capitalize()

def closest_monster(max_range):
	closest_enemy = None
	closest_dist = max_range + 1
	
	for obj in objects:
		if obj.fighter and not obj == player and (obj.x, obj.y) in visible_tiles:
			dist = player.distance_to(obj)
			if dist < closest_dist:
				closest_enemy = obj
				closest_dist = dist
	return closest_enemy

def target_tile(max_range=None):
	global mouse_coord
	
	while True:
		tdl.flush()
		clicked = False
		for event in tdl.event.get():
			if event.type == 'MOUSEMOTION': mouse_coord = event.cell
			if event.type == 'MOUSEDOWN': clicked = True
			elif ((event.type == 'MOUSEDOWN' and event.button == 'RIGHT') or 
					(event.type == 'KEYDOWN' and event.key == 'ESCAPE')):
				return (None, None)
		render_all()
		
		x = mouse_coord[0]
		y = mouse_coord[1]
		if (clicked and mouse_coord in visible_tiles and
			(max_range is None or player.distance(x, y) <= max_range)):
			return mouse_coord

def target_monster(max_range=None):
	while True:
		(x, y) = target_tile(max_range)
		if x is None:  #player cancelled
			return None
 
		#return the first clicked monster, otherwise continue looping
		for obj in objects:
			if obj.x == x and obj.y == y and obj.fighter and obj != player:
				return obj

def cast_heal(): #heal the player
	if player.fighter.hp == player.fighter.max_hp:
		message('You are already at full health.', colours.red)
		return 'cancelled'
 
	message('Your wounds start to mend!', colours.light_violet)
	player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
	# Find closest enemy inside a maximum range and damage it
	monster = closest_monster(LIGHTNING_RANGE)
	if monster is None:
		message('No enemy is close enough to strike.', colours.red)
		return 'cancelled'
 
	# Strike it!
	message('A lighting bolt strikes the ' + monster.name + ' with a loud thunder! The damage is '
		+ str(LIGHTNING_DAMAGE) + ' hit points.', colours.light_blue)
	monster.fighter.take_damage(LIGHTNING_DAMAGE)

def cast_confuse():
	message('Left-click an enemy to confuse it, or right-click to cancel.', colours.light_cyan)
	monster = target_monster(CONFUSE_RANGE)
	if monster is None:
		message('Cancelled')
		return 'cancelled'
	
	old_ai = monster.ai
	monster.ai = ConfusedMonster(old_ai)
	monster.ai.owner = monster
	message('The eyes of the ' + monster.name + ' look vacant, as he starts to ' +
			'stumble around!', colours.light_green)

def cast_fireball():
	message('Left-click a target tile for the fireball, or right-click to cancel.', colours.light_cyan)
	(x, y) = target_tile()
	if x is None:
		message('Cancelled')
		return 'cancelled'
	message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', colours.orange)
 
	for obj in objects:  #damage every fighter in range, including the player
		if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
			message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', colours.orange)
			obj.fighter.take_damage(FIREBALL_DAMAGE)

def save_game():
	with shelve.open('savegame', 'n') as savefile:
		savefile['my_map'] = my_map
		savefile['objects'] = objects
		savefile['player_index'] = objects.index(player)  #index of player in objects list
		savefile['inventory'] = inventory
		savefile['game_msgs'] = game_msgs
		savefile['game_state'] = game_state
		savefile.close()

def load_game():
	global my_map, objects, player, inventory, game_msgs, game_state
 
	with shelve.open('savegame', 'r') as savefile:
		my_map = savefile['my_map']
		objects = savefile['objects']
		player = objects[savefile['player_index']]  #get index of player in objects list and access it
		inventory = savefile['inventory']
		game_msgs = savefile['game_msgs']
		game_state = savefile['game_state']

# ----------------------------------------------------------------------
# Initialisation
# ----------------------------------------------------------------------

def new_game():
	global player, inventory, game_msgs, game_state
	
	# Create the player object
	fighter_component = Fighter(hp=30, defense=2, power=5, death_function=player_death)
	player = GameObject(0, 0, '@', 'player', colours.white, blocks=True, fighter=fighter_component)
	
	# Generate map
	make_map()
	
	game_state = 'playing'
	inventory = []
	
	game_msgs = []
	
	message('Welcome stranger! Prepare to perish in... THE ABYSS!', colours.red)
	
def play_game():
	global mouse_coord, fov_recompute
	
	player_action = None
	mouse_coord = (0, 0)
	fov_recompute = True
	con.clear()
	
	while not tdl.event.is_window_closed():
		# draw all objects in objects
		render_all()	
		tdl.flush()
		
		# Clear Previously occupied space
		for obj in objects: obj.clear()
		
		# Handle Keys
		player_action = handle_keys()
		if player_action == 'exit': break
		
		if game_state == 'playing' and player_action != 'didnt-take-turn':
			for obj in objects:
				if obj.ai:
					obj.ai.take_turn()

tdl.set_font('arial10x10.png', greyscale=True, altLayout=True)
root = tdl.init(SCREEN_WIDTH, SCREEN_HEIGHT, title="Roguelike", fullscreen=False)
con = tdl.Console(SCREEN_WIDTH, SCREEN_HEIGHT)
panel = tdl.Console(SCREEN_WIDTH, PANEL_HEIGHT)

main_menu()

	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
