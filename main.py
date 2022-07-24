import json
from dataclasses import dataclass, asdict
import datetime
import dacite
import curses
from curses import wrapper
from curses.textpad import Textbox, rectangle
import time
from enum import IntEnum
import sys
import copy
import asyncio
from desktop_notifier import DesktopNotifier
import subprocess

offset = 0

class Window(IntEnum):
    main = 0
    templates = 1

class ColumnType(IntEnum):
    description = 0
    start = 1
    requested_time = 2
    assigned_time = 3

class TodoStatus(IntEnum):
    uncompleted = 0
    completed = 1
    suspended = 2


@dataclass
class SubSlot:
    start: int
    reqtime: int
    assigned: int
    fixed_time: bool
    fixed_length: bool
    description: str

@dataclass
class Slot:
    start: int
    reqtime: int
    assigned: int
    fixed_time: bool
    fixed_length: bool
    description: str
    subslots: list[SubSlot]

@dataclass
class Template:
    name: str
    total_time: int
    start: int
    slots: list[Slot]

@dataclass
class Day:
    date: str
    total_time: int
    start: int
    slots: list[Slot]

@dataclass
class SlotBlock:
    startindex: int
    endindex: int
    blocklength: int
    fixedtime: int
    reqtime: int
    ratio: float

@dataclass
class Config:
    cursepath: str
    projectpath: str
    default_minutes: int
    desclimit: int
    autosave: bool
# sleep: list[float, float]


@dataclass
class Todo:
    priority: float
    description: str
    status: int # todostatus...
# suggested_time: int

@dataclass
class Mainclass:
    config: Config
    days: list[Day]
    todolist: list[Todo]

@dataclass
class Row:
    selected: int
    previous: int
    current: int
    bottom: int

@dataclass
class Column:
    selected: int
    maxindex = len(ColumnType) - 1


def current_minutes() -> int:
    now = datetime.datetime.now()
    return now.hour * 60 + now.minute


def min_to_time(mins: int) -> str:
    hrs = mins // 60
    mins = mins - hrs * 60
    
    hrs = str(hrs).rjust(2, "0")
    mins = str(mins).rjust(2, "0")

    return f"{hrs}:{mins}"


def intput(prompt: str, lower=float("-inf"), upper=float("inf"))-> int:
    assert isinstance(prompt, str)
    while True:
        try:
            value = int(input(prompt))
        except:
            print("invalid int")
            continue
        if not lower <= value <= upper:
            print("input out of bounds")
            continue
        return value


def calibrate_subslots(subslots, start, end):
    pass

def get_slotblocks(slots, end):
    slotblocks = []
    for index, slot in enumerate(slots):
        if not index or slot.fixed_time:
            slotblock = SlotBlock(index, 0, 0, 0, 0, 0)

        if slot.fixed_length:
            slotblock.fixedtime += slot.reqtime
        else:
            slotblock.reqtime   += slot.reqtime

        is_finalslot = index + 1 == len(slots)
        if is_finalslot or (nextslot := slots[index+1]).fixed_time:
            blockstart = slots[slotblock.startindex].start
            blockend   = end if is_finalslot else nextslot.start

            slotblock.endindex    = index + 1
            slotblock.blocklength = blockend - blockstart
            slotblock.ratio       = (slotblock.blocklength - slotblock.fixedtime) / slotblock.reqtime
            slotblocks.append(slotblock)
    return slotblocks

   




def calibrate_slots(day):
    slots = day.slots
    slots[0].start = day.start
    end_of_day = day.total_time + day.start

    slotblocks = get_slotblocks(slots, end_of_day)
    
    for slotblock in slotblocks:
        starttime = slots[slotblock.startindex].start
        for i in range(slotblock.startindex, slotblock.endindex):
            slot = slots[i]
            slot.start = starttime
            slot.assigned = slot.reqtime if slot.fixed_length else int(slot.reqtime * slotblock.ratio)
            starttime = slot.start + slot.assigned

    for slot in slots:
        if slot.subslots:
            calibrate_subslots(slot.subslots, slot.start, slot.start + slot.assigned)





def newslots(day, index):
    newslot = Slot(-1, mainclass.config.default_minutes, -1, False, False, "___", [])
    day.slots.insert(index + 1, newslot)



def template_to_day(template: Template, today)-> Day:

    newslot = Slot(
        template.start,
        1,
        -1,
        False,
        False,
        "___",
        )

    newday = Day(
            today,
            template.total_time,
            template.start,
            [Slot(
                0,
                reqtime,
                0,
                False,
                False,
                "...",
                [],
                )]

            )
    return newday



def init_main() -> Mainclass:
    default_template = Template(
            "blank",
            16 * 60,
            7 * 60,
            [],
            )
    
    config = Config("")

    
    newmain = Mainclass(
            config,
            [default_template],
            [new_day(config)]
            )
    return newmain


def fetch_current_day(mainclass: Mainclass, offset=0) -> Day:
    config = mainclass.config
    today = str((datetime.datetime.now() + datetime.timedelta(days=offset)).date())

    for day in mainclass.days:
        print(day.date, today)
        if day.date == today:
            return day




    newday = Day(
            today,
            16*60,
            450,
            [Slot(
                0,
                1,
                0,
                False,
                False,
                "...",
                [],
                )]
            )

    mainclass.days.append(newday)
    return newday


def get_cols(slot):
    lim = mainclass.config.desclimit
    desc = slot.description.ljust(lim," ")[:lim]
    if desc[-1] != " ":
        desc = desc[:-3:] + "..."
    start = min_to_time(slot.start).ljust(8, " ")
    req = str(slot.reqtime).ljust(4," ")
    ass = str(slot.assigned).ljust(4, " ")
    return desc, start, req, ass

def edit_description(screen, day, index):

    desc = []
    screen.move(index+1, 0)
    while True:
        try:
            keypressed = screen.getkey()
        except:
            continue
        if keypressed == "\n":
            day.slots[index].description = ''.join(desc)
            return 
        elif keypressed in ('KEY_BACKSPACE', '\b', '\x7f'):
            if not desc: continue
            y, x = screen.getyx()
            screen.move(index+1, x-1)
            screen.addstr(" ")
            screen.move(index+1, x-1)
            desc.pop()

        elif keypressed.isalnum() or keypressed == " ":
            screen.addstr(keypressed)
            desc.append(keypressed)
        else:
            screen.addstr(keypressed)


def edit_requested_time(screen, day, index, column, num):
    while True:
        match (keypressed := screen.getkey()):
            case '\n':
                day.slots[index].reqtime = int(num)
                if column == ColumnType.assigned_time:
                    day.slots[index].fixed_length = True
                return
            case 'KEY_EXIT':
                return
            case _:
                if keypressed.isnumeric():
                    num += keypressed

def int_format_time(num):
    if len(num) == 3:
        hrs = int(num[0])
        mins = int(num[1::])
    else:
        hrs = int(num[:2:])
        mins = int(num[2::])
    return hrs * 60 + mins


def debuglol(screen, var):
    var = str(var)
    screen.move(0,0)
    screen.addstr(var)
    screen.getch()


def load_curse_todos(cursepath):
    todolist = [] 
    with open(cursepath + "/todo", "r") as file:
        for line in file:
            priority = float(line[1])
            if priority == 0:
                priority = 5
            if line[3] == ">":
                description = line[45::].rstrip()
            else:
                description = line[4::].rstrip()
            status = TodoStatus.uncompleted
            todo = Todo(priority, 
                    description, 
                    status,
                    )

            todolist.append(todo)
    return todolist

def load_projects(projectpath):
    subprocess.run("python /home/tor/docs/prog/py/projects/main.py update", shell=True)
    time.sleep(0.2)
    todolist = []
    with open(projectpath) as f:
        data = json.load(f)
    projectlist = data["projects"]
    for project in projectlist:
        priority = project["priority"]
        description = project["desc"]
        status = TodoStatus.uncompleted
        todo = Todo(priority,
                description,
                status,
                )
        todolist.append(todo)
    return todolist

def sort_todos(todolist):
    sorted_todo = []
    for i in range(10):
        for todo in todolist:
            if todo.priority == i:
                sorted_todo.append(todo)
    return sorted_todo



def load_todos(config):
    curse_todos   = [] #load_curse_todos(config.cursepath)
    project_todos = [] #load_projects(config.projectpath)
    all_todos = curse_todos + project_todos
    return (sort_todos(all_todos))

def edit_start_time(screen, day, index, num):
    while True:
        keypressed = screen.getkey()
        if keypressed.isnumeric():
            num += keypressed
            if len(num) == 4:
                day.slots[index].start = int_format_time(num)
                return 
        if keypressed == '\n':
            if len(num) == 3:
                day.slots[index].start = int_format_time(num)
                return 
            return
        if keypressed == 'KEY_EXIT':
            return



def save_to_file(mainclass):
    with open('db.json', 'w') as fp:
        json.dump(asdict(mainclass), fp)

async def not_func(msg: tuple[str, str]):
    notify = DesktopNotifier()
    title, message = msg
    n = await notify.send(title=title + message, message=" ")

    await asyncio.sleep(10)  # wait a bit before clearing notification

    await notify.clear(n)  # removes the notification
    await notify.clear_all()  # removes all notifications for this app



def view_rows(screen, day, row, column):
    screen.clear()
    screen.addstr("viewing day " + str(day.date))
    slot_qty = row.bottom + 1
    line_index = 0

    for row_index, _row in enumerate(day.slots):
        screen.move(line_index + 1, 0)
        for col_index, _column in enumerate(get_cols(day.slots[row_index])):
            attributes = 0
            if col_index == ColumnType.start and _row.fixed_time == True:
                attributes |= curses.A_BOLD
            if col_index == ColumnType.requested_time and _row.fixed_length == True:
                attributes |= curses.A_BOLD
            if row_index == row.selected and col_index == column.selected:
                attributes |= curses.A_STANDOUT


            screen.addstr(_column, attributes)



        if slot_qty >= line_index + 1 and offset == 0:
            if _row.start <= current_minutes():
                if line_index + 1 == slot_qty or current_minutes() < day.slots[line_index + 1].start:
                    screen.addstr("🕑")
                    row.current = row_index

        if _row.subslots:
            for subslot in _row.subslots:
                line_index += 1
                screen.move(line_index + 1, 0)
                screen.addstr(" ↳   ")
                for i, x in enumerate(get_cols(subslot)):
                    if not i:
                        x = x[:-5:]
                    screen.addstr(x)

        line_index += 1
    screen.refresh()
    curses.curs_set(0)


def split(screen, day, row):
    if not (somevar := screen.getkey()).isnumeric():
        return
    somevar = int(somevar)

    reqtime = day.slots[row].reqtime // somevar
    for _ in range(somevar):
        newslot = Slot(
                0,
                reqtime,
                0,
                False,
                False,
                "...",
                [],
                )
        day.slots[row].subslots.append(newslot)





def handle_main_keys(screen, row, column):
    global selected_day
    global offset
    change = True

    selected_slot = selected_day.slots[row.selected]
    try:
        keypressed = screen.getkey()
    except Exception as e:
        if row.previous is not None and row.previous != row.current:
            msg = "Start new task!: ", selected_day.slots[row.current].description
            asyncio.run(not_func(msg))
        row.previous = row.current 
        return 



    match keypressed:
        case "KEY_DOWN" | "j":
            if row.selected != row.bottom:
                row.selected += 1
            change = False
        case "KEY_UP" | "k":
            if row.selected != 0:
                row.selected -= 1
            change = False
        case "KEY_LEFT" | "h":
            if column.selected != 0:
                column.selected -= 1
            change = False
        case "KEY_RIGHT" | "l":
            if column.selected != column.maxindex:
                column.selected += 1
            change = False
        case "i":
            newslots(selected_day, row.selected)
            row.selected += 1
            row.bottom += 1
            calibrate_slots(selected_day)
        case "I":
            newslots(selected_day, row.selected)
            row.selected += 1
            row.bottom += 1
            selected_day.slots[row.selected].description = mainclass.todolist[todoindex].description
            todoindex = (todoindex + 1) % (len(mainclass.todolist))
            calibrate_slots(selected_day)
        case "b":
            selected_slot.start = current_minutes()
            selected_slot.fixed_time = True
            selected_day.slots[row.selected - 1].fixed_length = False 
            calibrate_slots(selected_day)
        case "d":
            row.selected += 1
            row.bottom   += 1
            newslot = copy.deepcopy(selected_slot)
            selected_day.slots.insert(row.selected, newslot)
            calibrate_slots(selected_day)
        case "D":
            halftime = selected_day.slots[row.selected].reqtime // 2
            copiedslot = copy.deepcopy(selected_day.slots[row.selected])

            selected_day.slots[row.selected].reqtime = halftime
            copiedslot.reqtime = halftime
            copiedslot.fixed_time = False

            selected_day.slots.insert(row.selected, copiedslot)

            row.selected += 1
            row.bottom   +=1

            calibrate_slots(selected_day)
        case "s":
            save_to_file(mainclass)
        case "e":
            row.selected = row.current
        case "t":
            pass
        #return Window.templates
        case "z":
            selected_day.slots[row.selected].reqtime = selected_day.slots[row.selected].assigned
        case "x":
            split(screen, selected_day, row.selected)
        case "o":
            todoindex = (todoindex + 1) % len(mainclass.todolist)
            selected_day.slots[row.selected].description = mainclass.todolist[todoindex].description
        case "O":
            todoindex -= 1
            if todoindex == -1:
                todoindex = len(mainclass.todolist) - 1
            selected_day.slots[row.selected].description = mainclass.todolist[todoindex].description

        case "r":
            if row.selected:
                prevslot = selected_day.slots[row.selected - 1]
                if not (prevslot.fixed_time and selected_slot.fixed_time):
                    selected_day.slots[row.selected], selected_day.slots[row.selected - 1] = selected_day.slots[row.selected - 1], selected_day.slots[row.selected]
                    row.selected -= 1
                    calibrate_slots(selected_day)
        case "f":
            if row.selected != len(selected_day.slots) - 1:
                nextslot = selected_day.slots[row.selected + 1]
                if not (nextslot.fixed_time and selected_slot.fixed_time):
                    selected_day.slots[row.selected], selected_day.slots[row.selected + 1] = selected_day.slots[row.selected + 1], selected_day.slots[row.selected]
                    row.selected += 1
                    calibrate_slots(selected_day)

        case "m":
            offset += 1
            selected_day = fetch_current_day(mainclass, offset=offset)
            row.bottom = len(selected_day.slots) - 1
            row.selected = 0
            calibrate_slots(selected_day)
        case "n":
            offset -= 1
            selected_day = fetch_current_day(mainclass, offset=offset)
            row.bottom = len(selected_day.slots) - 1
            row.selected = 0
            calibrate_slots(selected_day)
        case "M":
            offset += 7
            selected_day = fetch_current_day(mainclass, offset=offset)
            row.bottom = len(selected_day.slots) - 1
            row.selected = 0
            calibrate_slots(selected_day)
        case "N":
            offset -= 7
            selected_day = fetch_current_day(mainclass, offset=offset)
            row.bottom = len(selected_day.slots) - 1
            row.selected = 0
            calibrate_slots(selected_day)
        case "KEY_DC":
            del selected_day.slots[row.selected]
            row.bottom -= 1
            if row.bottom == -1:
                newslots(selected_day, 0)
                row.selected = 0
                row.bottom = 0
            if row.selected == row.bottom + 1:
                row.selected -= 1
                selected_day.slots[row.selected].fixed_length = False
            calibrate_slots(selected_day)
        case "KEY_HOME" | "KEY_PPAGE":
            row.selected = 0
        case "KEY_END" | "KEY_NPAGE":
            row.selected = row.bottom
        case "\n": # enter-key
            match column.selected:
                case ColumnType.assigned_time | ColumnType.requested_time:
                    if not (row.selected == row.bottom and selected_slot.fixed_time):
                        selected_slot.fixed_length = not selected_slot.fixed_length
                case ColumnType.start:
                    selected_slot.fixed_time = not selected_slot.fixed_time
                    selected_day.slots[row.selected - 1].fixed_length = False
                case ColumnType.description:
                    edit_description(screen, selected_day, row.selected)
            calibrate_slots(selected_day)

        case wildcard:
            if wildcard.isnumeric():
                match column.selected:
                    case ColumnType.requested_time | ColumnType.assigned_time:
                        edit_requested_time(screen, selected_day, row.selected, column.selected, wildcard)
                        calibrate_slots(selected_day)
                    case ColumnType.start:
                        edit_start_time(screen, selected_day, row.selected, wildcard)
                        if row.selected:
                            selected_day.slots[row.selected].fixed_time = True
                            selected_day.slots[row.selected - 1].fixed_length = False
                        else:
                            selected_day.start = selected_day.slots[row.selected].start
                        calibrate_slots(selected_day)
        
    if change and mainclass.config.autosave:
        save_to_file(mainclass)



def view_main(stdscr, mainclass):
#    global selected_day

    column = Column(0)

    row = Row(0, None, None, 0)
    row.bottom = len(selected_day.slots) - 1
    
    offset = 0
    todoindex = 0

    stdscr.clear()
    curses.halfdelay(150)


    while True:
        view_rows       (stdscr, selected_day, row, column)
        handle_main_keys(stdscr,  row, column)
        







try:
    with open('db.json') as f:
        for line in f:
            loaded_dict = json.loads(line)
    mainclass = dacite.from_dict(data_class=Mainclass, data=loaded_dict)

    print("maybe no exception!")
except SyntaxError as e:
    print("exception!!!", e)
    sys.exit(e)
    




    


def main(stdscr):
    window = Window.main
    while True:
        match window:
            case Window.main:
                window = view_main(stdscr, mainclass)
            case Window.templates:
                sys.exit("template test")

def view_apts(mainclass):
    with open(mainclass.config.cursepath + "/todo", "r") as f:
        for l in f:
            print(l)
    input()






mainclass.todolist = load_todos(mainclass.config)

#for day in loaded_dict["days"]:
 #   for slot in day["slots"]:
  #      slot["subslots"] = []

#with open('db.json', 'w') as fp:
 #   json.dump(loaded_dict, fp)

#save_to_file(mainclass)
#sys.exit("cool")


selected_day = fetch_current_day(mainclass)
#sys.exit(str(len(selected_day.slots)))

wrapper(main)























