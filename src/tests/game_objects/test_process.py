import pytest
from constants import LAST_ALIVE_STARVATION_LEVEL, DEAD_STARVATION_LEVEL, MAX_PAGES_PER_PROCESS
from engine.game_event import GameEvent
from engine.game_event_type import GameEventType
from engine.random import Random

from game_objects.process import Process

class TestProcess:
    @property
    def starvation_interval(self):
        return 10000

    @property
    def time_to_unstarve(self):
        return 5000

    @pytest.fixture
    def game(self, game, monkeypatch):
        """
        Overrides game fixture defined in src/tests/conftest.py.
        """
        monkeypatch.setattr(game.process_manager, 'terminate_process', lambda process, by_user: True)
        monkeypatch.setattr(game.process_manager, 'del_process', lambda process: None)
        return game

    @pytest.fixture
    def game_custom_config(self, game_custom_config, monkeypatch):
        """
        Overrides game_custom_config fixture defined in src/tests/conftest.py.
        """
        def create_game(game_config):
            game = game_custom_config(game_config)
            monkeypatch.setattr(game.process_manager, 'terminate_process', lambda process, by_user: True)
            monkeypatch.setattr(game.process_manager, 'del_process', lambda process: None)
            return game
        return create_game

    def test_initial_property_values(self, game):
        process = Process(1, game)

        assert process.pid == 1
        assert process.has_cpu == False
        assert process.is_waiting_for_io == False
        assert process.is_waiting_for_page == False
        assert process.is_blocked == False
        assert process.has_ended == False
        assert process.starvation_level == 1
        assert process.display_blink_color == False
        assert process.current_state_duration == 0
        assert process.is_progressing_to_happiness == False

    def test_starvation_when_idle(self, game):
        process = Process(1, game)

        for i in range(0, LAST_ALIVE_STARVATION_LEVEL):
            process.update(i * self.starvation_interval, [])
            assert process.starvation_level == i + 1

    def test_max_starvation(self, game):
        process = Process(1, game)

        for i in range(0, LAST_ALIVE_STARVATION_LEVEL):
            process.update(i * self.starvation_interval, [])

        assert process.starvation_level == LAST_ALIVE_STARVATION_LEVEL

        process.update(DEAD_STARVATION_LEVEL * self.starvation_interval, [])

        assert process.starvation_level == DEAD_STARVATION_LEVEL
        assert process.has_ended == True

    def test_use_cpu_when_first_cpu_is_available(self, game):
        process = Process(1, game)

        assert process.has_cpu == False
        for i in range(0, game.config['num_cpus']):
            assert game.process_manager.cpu_list[i].process == None

        process.use_cpu()

        assert process.has_cpu == True
        assert game.process_manager.cpu_list[0].process == process
        for i in range(1, game.config['num_cpus']):
            assert game.process_manager.cpu_list[i].process == None

        assert process.is_waiting_for_io == False
        assert process.is_waiting_for_page == False
        assert process.is_blocked == False
        assert process.has_ended == False

    def test_use_cpu_when_first_cpu_is_unavailable(self, game):
        process = Process(1, game)

        assert process.has_cpu == False
        for i in range(0, game.config['num_cpus']):
            assert game.process_manager.cpu_list[i].process == None

        game.process_manager.cpu_list[0].process = Process(2, game)
        process.use_cpu()

        assert process.has_cpu == True
        assert game.process_manager.cpu_list[0].process.pid == 2
        assert game.process_manager.cpu_list[1].process == process
        for i in range(2, game.config['num_cpus']):
            assert game.process_manager.cpu_list[i].process == None

        assert process.is_waiting_for_io == False
        assert process.is_waiting_for_page == False
        assert process.is_blocked == False
        assert process.has_ended == False

    def test_use_cpu_when_all_cpus_are_unavailable(self, game):
        process = Process(1, game)

        assert process.has_cpu == False
        for i in range(0, game.config['num_cpus']):
            assert game.process_manager.cpu_list[i].process == None

        for i in range(0, game.config['num_cpus']):
            game.process_manager.cpu_list[i].process = Process(i + 2, game)

        process.use_cpu()

        assert process.has_cpu == False
        for i in range(0, game.config['num_cpus']):
            assert game.process_manager.cpu_list[i].process.pid == i + 2

        assert process.is_waiting_for_io == False
        assert process.is_waiting_for_page == False
        assert process.is_blocked == False
        assert process.has_ended == False

    def test_use_cpu_when_already_using_cpu(self, game):
        process = Process(1, game)

        process.use_cpu()
        process.use_cpu()

        assert process.has_cpu == True
        assert game.process_manager.cpu_list[0].process == process
        for i in range(1, game.config['num_cpus']):
            assert game.process_manager.cpu_list[i].process == None

        assert process.is_waiting_for_io == False
        assert process.is_waiting_for_page == False
        assert process.is_blocked == False
        assert process.has_ended == False

    def test_yield_cpu(self, game):
        process = Process(1, game)

        for i in range(0, game.config['num_cpus'] - 1):
            game.process_manager.cpu_list[i].process = Process(i + 2, game)

        process.use_cpu()

        process.yield_cpu()
        assert process.has_cpu == False
        for i in range(0, game.config['num_cpus'] - 1):
            assert game.process_manager.cpu_list[i].process.pid == i + 2
        assert game.process_manager.cpu_list[3].process == None

        assert process.is_waiting_for_io == False
        assert process.is_waiting_for_page == False
        assert process.is_blocked == False
        assert process.has_ended == False

    def test_yield_cpu_when_already_idle(self, game):
        process = Process(1, game)

        process.yield_cpu()
        assert process.has_cpu == False
        for i in range(0, game.config['num_cpus']):
            assert game.process_manager.cpu_list[i].process == None

        assert process.is_waiting_for_io == False
        assert process.is_waiting_for_page == False
        assert process.is_blocked == False
        assert process.has_ended == False

    def test_toggle(self, game):
        process = Process(1, game)

        process.toggle()
        assert process.has_cpu == True

        process.toggle()
        assert process.has_cpu == False

    def test_unstarvation(self, game):
        process = Process(1, game)

        current_time = 0

        for i in range(1, LAST_ALIVE_STARVATION_LEVEL):
            current_time += self.starvation_interval
            process.update(current_time, [])

        process.use_cpu()
        assert process.starvation_level == LAST_ALIVE_STARVATION_LEVEL

        current_time += self.time_to_unstarve
        process.update(current_time, [])
        assert process.starvation_level == 0

    def test_graceful_termination(self, game_custom_config, monkeypatch):
        game = game_custom_config({
            'name': 'Test Config',
            'num_cpus': 4,
            'num_processes_at_startup': 14,
            'num_ram_rows': 8,
            'new_process_probability': 0,
            'io_probability': 0,
            'graceful_termination_probability': 0.01
        })

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: min)

        process = Process(1, game)
        process.use_cpu()

        process.update(1000, [])

        assert process.has_ended == True
        assert process.starvation_level == 0        

    def test_use_cpu_min_page_creation(self, game, monkeypatch):
        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: min)

        process = Process(1, game)

        with pytest.raises(KeyError):
            game.page_manager.get_page(1, 0)

        process.use_cpu()

        assert game.page_manager.get_page(1, 0).pid == 1
        for i in range(1, MAX_PAGES_PER_PROCESS):
            with pytest.raises(KeyError):
                game.page_manager.get_page(1, i)

    def test_use_cpu_max_page_creation(self, game, monkeypatch):
        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        process = Process(1, game)

        with pytest.raises(KeyError):
            game.page_manager.get_page(1, 0)

        process.use_cpu()

        for i in range(1, MAX_PAGES_PER_PROCESS):
            assert game.page_manager.get_page(1, i).pid == 1
        with pytest.raises(KeyError):
            game.page_manager.get_page(1, 4)

    def test_new_page_creation_while_running(self, game, monkeypatch):
        process = Process(1, game)

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: min)

        process.use_cpu()

        assert game.page_manager.get_page(1, 0).pid == 1
        with pytest.raises(KeyError):
            game.page_manager.get_page(1, 1)

        process.update(1000, [])

        assert game.page_manager.get_page(1, 0).pid == 1
        assert game.page_manager.get_page(1, 1).pid == 1

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        process.update(2000, [])

        assert game.page_manager.get_page(1, 0).pid == 1
        assert game.page_manager.get_page(1, 1).pid == 1
        with pytest.raises(KeyError):
            game.page_manager.get_page(1, 2)

    def test_use_cpu_when_already_has_pages(self, game, monkeypatch):
        process = Process(1, game)

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: min)
        process.use_cpu()

        process.yield_cpu()

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)
        process.use_cpu()

        assert game.page_manager.get_page(1, 0).pid == 1
        for i in range(1, MAX_PAGES_PER_PROCESS):
            with pytest.raises(KeyError):
                game.page_manager.get_page(1, i)

    def test_use_cpu_sets_pages_to_in_use(self, game, monkeypatch):
        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        process = Process(1, game)

        process.use_cpu()
        for i in range(0, MAX_PAGES_PER_PROCESS):
            assert game.page_manager.get_page(1, i).in_use == True

        process.yield_cpu()
        process.use_cpu()
        for i in range(0, MAX_PAGES_PER_PROCESS):
            assert game.page_manager.get_page(1, i).in_use == True

    def test_yield_cpu_sets_pages_to_not_in_use(self, game, monkeypatch):
        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        process = Process(1, game)

        process.use_cpu()
        process.yield_cpu()

        for i in range(0, MAX_PAGES_PER_PROCESS):
            assert game.page_manager.get_page(1, i).in_use == False

    def test_set_page_to_swap_while_running(self, game, monkeypatch):
        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        process = Process(1, game)

        process.use_cpu()

        game.page_manager.get_page(1, 0).swap()
        assert game.page_manager.get_page(1, 0).in_swap == True

        process.update(0, [])

        assert process.is_blocked == True
        assert process.is_waiting_for_page == True
        assert process.is_waiting_for_io == False

    def test_set_page_to_swap_before_running(self, game, monkeypatch):
        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        process = Process(1, game)

        process.use_cpu()
        process.yield_cpu()

        game.page_manager.get_page(1, 0).swap()
        assert game.page_manager.get_page(1, 0).in_swap == True

        process.use_cpu()

        process.update(0, [])

        assert process.is_blocked == True
        assert process.is_waiting_for_page == True
        assert process.is_waiting_for_io == False

    def test_remove_page_from_swap_while_running(self, game, monkeypatch):
        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        process = Process(1, game)

        process.use_cpu()

        game.page_manager.get_page(1, 0).swap()
        process.update(0, [])
        assert process.is_blocked == True

        game.page_manager.get_page(1, 0).swap()
        process.update(0, [])

        assert process.is_blocked == False
        assert process.is_waiting_for_page == False
        assert process.is_waiting_for_io == False

    def test_yield_cpu_while_waiting_for_page(self, game, monkeypatch):
        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        process = Process(1, game)

        process.use_cpu()

        game.page_manager.get_page(1, 0).swap()
        process.update(0, [])
        assert process.is_waiting_for_page == True

        process.yield_cpu()
        process.update(0, [])

        assert process.is_blocked == False
        assert process.is_waiting_for_page == False
        assert process.is_waiting_for_io == False

    def test_starvation_while_waiting_for_page(self, game, monkeypatch):
        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        process = Process(1, game)

        process.use_cpu()

        game.page_manager.get_page(1, 0).swap()
        process.update(0, [])
        assert process.is_waiting_for_page == True

        for i in range(1, LAST_ALIVE_STARVATION_LEVEL):
            process.update(i * self.starvation_interval, [])
            assert process.starvation_level == i + 1

        process.update(LAST_ALIVE_STARVATION_LEVEL * self.starvation_interval, [])
        assert process.starvation_level == DEAD_STARVATION_LEVEL
        assert process.has_ended == True

    def test_page_deletion_when_process_is_killed(self, game, monkeypatch):
        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        process = Process(1, game)

        process.use_cpu()
        game.page_manager.get_page(1, 0).swap()

        for i in range(1, DEAD_STARVATION_LEVEL):
            process.update(i * self.starvation_interval, [])
        assert process.has_ended == True

        with pytest.raises(KeyError):
            for i in range(1, 5):
                game.page_manager.get_page(1, i)

    def test_page_deletion_when_process_is_gracefully_terminated(self, game_custom_config, monkeypatch):
        game = game_custom_config({
            'name': 'Test Config',
            'num_cpus': 4,
            'num_processes_at_startup': 14,
            'num_ram_rows': 8,
            'new_process_probability': 0,
            'io_probability': 0,
            'graceful_termination_probability': 0.01
        })

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        process = Process(1, game)
        process.use_cpu()
        process.update(1000, [])
        assert process.has_ended == False
        assert game.page_manager.get_page(1, 0).pid == 1

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: min)

        process.update(2000, [])

        assert process.has_ended == True
        assert process.starvation_level == 0

        with pytest.raises(KeyError):
            for i in range(0, 5):
                game.page_manager.get_page(1, i)

    def test_process_blocks_for_io_event(self, game_custom_config, monkeypatch):
        game = game_custom_config({
            'name': 'Test Config',
            'num_cpus': 4,
            'num_processes_at_startup': 14,
            'num_ram_rows': 8,
            'new_process_probability': 0,
            'io_probability': 0.1,
            'graceful_termination_probability': 0
        })

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: min)

        process = Process(1, game)

        process.use_cpu()
        process.update(0, [])
        assert process.is_waiting_for_io == False

        process.update(1000, [])

        assert process.is_blocked == True
        assert process.is_waiting_for_io == True
        assert process.is_waiting_for_page == False

    def test_process_continues_when_no_io_event(self, game_custom_config, monkeypatch):
        game = game_custom_config({
            'name': 'Test Config',
            'num_cpus': 4,
            'num_processes_at_startup': 14,
            'num_ram_rows': 8,
            'new_process_probability': 0,
            'io_probability': 0.1,
            'graceful_termination_probability': 0
        })

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        process = Process(1, game)

        process.use_cpu()
        process.update(0, [])
        assert process.is_waiting_for_io == False

        process.update(1000, [])

        assert process.is_blocked == False
        assert process.is_waiting_for_io == False
        assert process.is_waiting_for_page == False

    def test_starvation_while_waiting_for_io_event(self, game_custom_config, monkeypatch):
        game = game_custom_config({
            'name': 'Test Config',
            'num_cpus': 4,
            'num_processes_at_startup': 14,
            'num_ram_rows': 8,
            'new_process_probability': 0,
            'io_probability': 0.1,
            'graceful_termination_probability': 0
        })

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: min)

        process = Process(1, game)

        process.use_cpu()
        process.update(1000, [])
        assert process.is_waiting_for_io == True

        for i in range(1, LAST_ALIVE_STARVATION_LEVEL):
            process.update(i * self.starvation_interval, [])
            assert process.starvation_level == i + 1

        process.update(LAST_ALIVE_STARVATION_LEVEL * self.starvation_interval, [])
        assert process.starvation_level == DEAD_STARVATION_LEVEL
        assert process.has_ended == True
        assert process.is_blocked == False
        assert process.is_waiting_for_io == False

    def test_process_unblocks_when_io_event_is_processed(self, game_custom_config, monkeypatch):
        game = game_custom_config({
            'name': 'Test Config',
            'num_cpus': 4,
            'num_processes_at_startup': 14,
            'num_ram_rows': 8,
            'new_process_probability': 0,
            'io_probability': 0.1,
            'graceful_termination_probability': 0
        })

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: min)

        process = Process(1, game)

        process.use_cpu()
        process.update(1000, [])
        assert process.is_waiting_for_io == True

        game.process_manager.io_queue.update(1000, [])
        game.process_manager.io_queue.process_events()

        assert process.is_blocked == False
        assert process.is_waiting_for_io == False

    def test_no_io_event_at_last_alive_starvation_level(self, game_custom_config, monkeypatch):
        game = game_custom_config({
            'name': 'Test Config',
            'num_cpus': 4,
            'num_processes_at_startup': 14,
            'num_ram_rows': 8,
            'new_process_probability': 0,
            'io_probability': 0.1,
            'graceful_termination_probability': 0
        })

        process1 = Process(1, game)
        process2 = Process(2, game)

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        current_time = 0
        for i in range(1, LAST_ALIVE_STARVATION_LEVEL):
            current_time += self.starvation_interval
            process1.update(current_time, [])

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: min)

        process1.use_cpu()
        process2.use_cpu()

        assert process1.starvation_level == LAST_ALIVE_STARVATION_LEVEL
        assert process2.starvation_level == 1
        assert process1.is_waiting_for_io == False
        assert process2.is_waiting_for_io == False

        current_time += 1000
        process1.update(current_time, [])
        process2.update(current_time, [])

        assert process1.starvation_level == LAST_ALIVE_STARVATION_LEVEL
        assert process1.is_waiting_for_io == False
        assert process2.is_waiting_for_io == True

    def test_io_cooldown(self, game_custom_config, monkeypatch):
        game = game_custom_config({
            'name': 'Test Config',
            'num_cpus': 4,
            'num_processes_at_startup': 14,
            'num_ram_rows': 8,
            'new_process_probability': 0,
            'io_probability': 0.1,
            'graceful_termination_probability': 0
        })

        process1 = Process(1, game)
        process2 = Process(2, game)

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: min)

        process1.use_cpu()
        process1.update(1000, [])
        assert process1.is_waiting_for_io == True

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: max)

        process2.use_cpu()
        process2.update(1000, [])
        assert process2.is_waiting_for_io == False

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: min)

        game.process_manager.io_queue.update(1000, [])
        game.process_manager.io_queue.process_events()
        assert process1.is_waiting_for_io == False

        process1.update(2000, [])
        process2.update(2000, [])
        assert process1.is_waiting_for_io == False
        assert process2.is_waiting_for_io == True

    def test_io_cooldown_deactivation(self, game_custom_config, monkeypatch):
        game = game_custom_config({
            'name': 'Test Config',
            'num_cpus': 4,
            'num_processes_at_startup': 14,
            'num_ram_rows': 8,
            'new_process_probability': 0,
            'io_probability': 0.1,
            'graceful_termination_probability': 0
        })

        process = Process(1, game)

        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: min)

        process.use_cpu()
        process.update(1000, [])
        assert process.is_waiting_for_io == True

        game.process_manager.io_queue.update(1000, [])
        game.process_manager.io_queue.process_events()
        assert process.is_waiting_for_io == False

        process.yield_cpu()
        process.use_cpu()
        process.update(2000, [])
        assert process.is_waiting_for_io == True

    def test_movement_animation(self, game):
        process = Process(1, game)

        target_x = 500
        target_y = 1000

        process.view.x = 0
        process.view.y = 0
        process.view.target_x = target_x
        process.view.target_y = target_y

        counter = 0
        while process.view.target_x != None or process.view.target_y != None:
            counter += 1
            process.update(counter, [])
            assert counter < 100 # prevents infinite loop if test fails

        assert process.view.x == target_x
        assert process.view.y == target_y

    def test_click_when_idle(self, game):
        process = Process(1, game)

        mouse_click_event = GameEvent(GameEventType.MOUSE_LEFT_CLICK, { 'position': (process.view.x, process.view.y) })
        process.update(1000, [mouse_click_event])

        assert process.has_cpu == True
        assert process.view.target_x == game.process_manager.cpu_list[0].view.x
        assert process.view.target_y == game.process_manager.cpu_list[0].view.y

    def test_click_during_moving_animation(self, game):
        process = Process(1, game)
        process.use_cpu()

        assert process.has_cpu == True
        assert process.view.y != process.view.target_y

        mouse_click_event = GameEvent(GameEventType.MOUSE_LEFT_CLICK, { 'position': (process.view.x, process.view.y) })
        process.update(1000, [mouse_click_event])
        assert process.has_cpu == True

    def test_click_when_running(self, game):
        process = Process(1, game)
        game.process_manager.cpu_list[0].process = Process(2, game) # to force process to use a CPU with a different x position than itself
        process.use_cpu()

        assert process.has_cpu == True

        process.view.x = process.view.target_x
        process.view.y = process.view.target_y
        process.view.target_x = None
        process.view.target_y = None

        mouse_click_event = GameEvent(GameEventType.MOUSE_LEFT_CLICK, { 'position': (process.view.x, process.view.y) })
        process.update(1000, [mouse_click_event])

        assert process.has_cpu == False
        assert process.view.target_x == game.process_manager.process_slots[0].view.x
        assert process.view.target_y == game.process_manager.process_slots[0].view.y

    def test_click_when_gracefully_terminated(self, game_custom_config, monkeypatch):
        game = game_custom_config({
            'name': 'Test Config',
            'num_cpus': 4,
            'num_processes_at_startup': 14,
            'num_ram_rows': 8,
            'new_process_probability': 0,
            'io_probability': 0,
            'graceful_termination_probability': 0.01
        })
        monkeypatch.setattr(Random, 'get_number', lambda self, min, max: min)

        process = Process(1, game)
        process.use_cpu()
        process.update(1000, [])
        process.view.x = process.view.target_x
        process.view.y = process.view.target_y
        process.view.target_x = process.view.target_y = None

        assert process.has_ended == True

        mouse_click_event = GameEvent(GameEventType.MOUSE_LEFT_CLICK, { 'position': (process.view.x, process.view.y) })
        process.update(2000, [mouse_click_event])

        assert process.view.target_y <= -process.view.height

    def test_blinking_animation(self, game):
        process = Process(1, game)

        process.use_cpu()
        game.page_manager.get_page(1, 0).swap()

        previous_blink_value = process.display_blink_color
        for i in range(1, 5):
            process.update(i * 200, [])
            assert process.display_blink_color != previous_blink_value
            previous_blink_value = process.display_blink_color

    def test_blinking_animation_deactivation(self, game):
        process = Process(1, game)

        process.use_cpu()
        game.page_manager.get_page(1, 0).swap()
        process.update(1000, [])

        game.page_manager.get_page(1, 0).swap()
        process.update(2000, [])

        previous_blink_value = process.display_blink_color
        for i in range(1, 5):
            process.update(i * 200, [])
            assert process.display_blink_color == previous_blink_value
            previous_blink_value = process.display_blink_color