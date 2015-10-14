# sync.py
#
# Different test scenarios designed to run under management of a kernel

import unittest
from collections import deque

from ..import *

# ---- Synchronization primitives

class TestEvent(unittest.TestCase):
    def test_event_get_wait(self):
        kernel = get_kernel()
        results = []
        async def event_setter(evt, seconds):
              results.append('sleep')
              await sleep(seconds)
              results.append('event_set')
              evt.set()

        async def event_waiter(evt):
              results.append('wait_start')
              results.append(evt.is_set())
              await evt.wait()
              results.append('wait_done')
              results.append(evt.is_set())
              evt.clear()
              results.append(evt.is_set())

        evt = Event()
        kernel.add_task(event_waiter(evt))
        kernel.add_task(event_setter(evt, 1))
        kernel.run()
        self.assertEqual(results, [
                'wait_start',
                False,
                'sleep',
                'event_set',
                'wait_done',
                True,
                False
                ])

    def test_event_get_immediate(self):
        kernel = get_kernel()
        results = []
        async def event_setter(evt):
              results.append('event_set')
              evt.set()

        async def event_waiter(evt, seconds):
              results.append('sleep')
              await sleep(seconds)
              results.append('wait_start')
              await evt.wait()
              results.append('wait_done')

        evt = Event()
        kernel.add_task(event_waiter(evt, 1))
        kernel.add_task(event_setter(evt))
        kernel.run()
        self.assertEqual(results, [
                'sleep',
                'event_set',
                'wait_start',
                'wait_done',
                ])


    def test_event_wait_cancel(self):
        kernel = get_kernel()
        results = []
        async def event_waiter(evt):
              results.append('event_wait')
              try:
                   await evt.wait()
              except CancelledError:
                   results.append('event_cancel')

        async def event_cancel(seconds):
              evt = Event()
              taskid = kernel.add_task(event_waiter(evt))
              results.append('sleep')
              await sleep(seconds)
              results.append('cancel_start')
              kernel.cancel_task(taskid)
              results.append('cancel_done')

        kernel.add_task(event_cancel(1))
        kernel.run()
        self.assertEqual(results, [
                'sleep',
                'event_wait',
                'cancel_start',
                'cancel_done',
                'event_cancel',
                ])

    def test_event_wait_timeout(self):
        kernel = get_kernel()
        results = []
        async def event_waiter(evt):
              results.append('event_wait')
              try:
                   await evt.wait(timeout=0.5)
              except TimeoutError:
                   results.append('event_timeout')

        async def event_run(seconds):
              evt = Event()
              taskid = kernel.add_task(event_waiter(evt))
              results.append('sleep')
              await sleep(seconds)
              results.append('sleep_done')

        kernel.add_task(event_run(1))
        kernel.run()
        self.assertEqual(results, [
                'sleep',
                'event_wait',
                'event_timeout',
                'sleep_done',
                ])

class TestLock(unittest.TestCase):
    def test_lock_sequence(self):
        kernel = get_kernel()
        results = []
        async def worker(lck, label):
              results.append(label + ' wait')
              results.append(lck.locked())
              async with lck:
                   results.append(label + ' acquire')
                   await sleep(0.25)
              results.append(label + ' release')

        lck = Lock()
        kernel.add_task(worker(lck, 'work1'))
        kernel.add_task(worker(lck, 'work2'))
        kernel.add_task(worker(lck, 'work3'))
        kernel.run()
        self.assertEqual(results, [
                'work1 wait',
                False,
                'work1 acquire',
                'work2 wait',
                True,
                'work3 wait',
                True,
                'work1 release',
                'work2 acquire',
                'work2 release',
                'work3 acquire',
                'work3 release',
                ])

    def test_lock_acquire_cancel(self):
        kernel = get_kernel()
        results = []
        async def worker(lck):
              results.append('lock_wait')
              try:
                  async with lck:
                       results.append('never here')
              except CancelledError:
                  results.append('lock_cancel')

        async def worker_cancel(seconds):
              lck = Lock()
              taskid = kernel.add_task(worker(lck))
              async with lck:
                  results.append('sleep')
                  await sleep(seconds)
                  results.append('cancel_start')
                  kernel.cancel_task(taskid)
                  results.append('cancel_done')

        kernel.add_task(worker_cancel(1))
        kernel.run()
        self.assertEqual(results, [
                'sleep',
                'lock_wait',
                'cancel_start',
                'cancel_done',
                'lock_cancel',
                ])


    def test_lock_acquire_timeout(self):
        kernel = get_kernel()
        results = []
        async def worker(lck):
              results.append('lock_wait')
              try:
                  await lck.acquire(timeout=0.5)
                  results.append('never here')
                  lck.release()
              except TimeoutError:
                  results.append('lock_timeout')

        async def worker_timeout(seconds):
              lck = Lock()
              taskid = kernel.add_task(worker(lck))
              async with lck:
                  results.append('sleep')
                  await sleep(seconds)
                  results.append('sleep_done')

        kernel.add_task(worker_timeout(1))
        kernel.run()
        self.assertEqual(results, [
                'sleep',
                'lock_wait',
                'lock_timeout',
                'sleep_done',
                ])


class TestSemaphore(unittest.TestCase):
    def test_sema_sequence(self):
        kernel = get_kernel()
        results = []
        async def worker(sema, label):
              results.append(label + ' wait')
              results.append(sema.locked())
              async with sema:
                   results.append(label + ' acquire')
                   await sleep(0.25)
              results.append(label + ' release')

        sema = Semaphore()
        kernel.add_task(worker(sema, 'work1'))
        kernel.add_task(worker(sema, 'work2'))
        kernel.add_task(worker(sema, 'work3'))
        kernel.run()
        self.assertEqual(results, [
                'work1 wait',
                False,
                'work1 acquire',
                'work2 wait',
                True,
                'work3 wait',
                True,
                'work1 release',
                'work2 acquire',
                'work2 release',
                'work3 acquire',
                'work3 release',
                ])

    def test_sema_sequence2(self):
        kernel = get_kernel()
        results = []
        async def worker(sema, label, seconds):
              results.append(label + ' wait')
              results.append(sema.locked())
              async with sema:
                   results.append(label + ' acquire')
                   await sleep(seconds)
              results.append(label + ' release')

        sema = Semaphore(2)
        kernel.add_task(worker(sema, 'work1', 0.25))
        kernel.add_task(worker(sema, 'work2', 0.30))
        kernel.add_task(worker(sema, 'work3', 0.35))
        kernel.run()
        self.assertEqual(results, [
                'work1 wait',            # Both work1 and work2 admitted
                False,
                'work1 acquire',
                'work2 wait',
                False,
                'work2 acquire',
                'work3 wait',
                True,
                'work1 release',         # work3 admitted after work1 release
                'work3 acquire',
                'work2 release',
                'work3 release',
                ])

    def test_sema_acquire_cancel(self):
        kernel = get_kernel()
        results = []
        async def worker(lck):
              results.append('lock_wait')
              try:
                  async with lck:
                       results.append('never here')
              except CancelledError:
                  results.append('lock_cancel')

        async def worker_cancel(seconds):
              lck = Semaphore()
              taskid = kernel.add_task(worker(lck))
              async with lck:
                  results.append('sleep')
                  await sleep(seconds)
                  results.append('cancel_start')
                  kernel.cancel_task(taskid)
                  results.append('cancel_done')

        kernel.add_task(worker_cancel(1))
        kernel.run()
        self.assertEqual(results, [
                'sleep',
                'lock_wait',
                'cancel_start',
                'cancel_done',
                'lock_cancel',
                ])


    def test_sema_acquire_timeout(self):
        kernel = get_kernel()
        results = []
        async def worker(lck):
              results.append('lock_wait')
              try:
                  await lck.acquire(timeout=0.5)
                  results.append('never here')
                  lck.release()
              except TimeoutError:
                  results.append('lock_timeout')

        async def worker_timeout(seconds):
              lck = Semaphore()
              taskid = kernel.add_task(worker(lck))
              async with lck:
                  results.append('sleep')
                  await sleep(seconds)
                  results.append('sleep_done')

        kernel.add_task(worker_timeout(1))
        kernel.run()
        self.assertEqual(results, [
                'sleep',
                'lock_wait',
                'lock_timeout',
                'sleep_done',
                ])

    def test_bounded(self):
        sema = BoundedSemaphore(1)
        with self.assertRaises(ValueError):
            sema.release()

class TestCondition(unittest.TestCase):
    def test_cond_sequence(self):
        kernel = get_kernel()
        results = []
        async def consumer(cond, q, label):
              while True:
                  async with cond:
                      if not q:
                          results.append(label + ' wait')
                          await cond.wait()
                      item = q.popleft()
                      if item is None:
                          break
                      results.append((label, item))
              results.append(label+' done') 

        async def producer(cond, q, count, nproducers):
             for n in range(count):
                 async with cond:
                     q.append(n)
                     results.append(('producing', n))
                     cond.notify()
                 await sleep(0.1)

             for n in range(nproducers):
                 async with cond:
                     q.append(None)
                     results.append(('ending', n))
                     cond.notify()
                 await sleep(0.1)
              
        cond = Condition()
        q = deque()
        kernel.add_task(consumer(cond, q, 'cons1'))
        kernel.add_task(consumer(cond, q, 'cons2'))
        kernel.add_task(producer(cond, q, 4, 2))
        kernel.run()
        self.assertEqual(results, [
                'cons1 wait',
                'cons2 wait',
                ('producing', 0),
                ('cons1', 0),
                'cons1 wait',
                ('producing', 1),
                ('cons2', 1),
                'cons2 wait',
                ('producing', 2),
                ('cons1', 2),
                'cons1 wait',
                ('producing', 3),
                ('cons2', 3),
                'cons2 wait',
                ('ending', 0),
                ('cons1 done'),
                ('ending', 1),
                ('cons2 done')
                ])

    def test_cond_wait_cancel(self):
        kernel = get_kernel()
        results = []
        async def worker(cond):
              try:
                  async with cond:
                       results.append('cond_wait')
                       await cond.wait()
                       results.append('never here')
              except CancelledError:
                  results.append('worker_cancel')

        async def worker_cancel(seconds):
              cond = Condition()
              taskid = kernel.add_task(worker(cond))
              results.append('sleep')
              await sleep(seconds)
              results.append('cancel_start')
              kernel.cancel_task(taskid)
              results.append('cancel_done')

        kernel.add_task(worker_cancel(1))
        kernel.run()
        self.assertEqual(results, [
                'sleep',
                'cond_wait',
                'cancel_start',
                'cancel_done',
                'worker_cancel',
                ])

    def test_cond_wait_timeout(self):
        kernel = get_kernel()
        results = []
        async def worker(cond):
              try:
                  async with cond:
                       results.append('cond_wait')
                       await cond.wait(timeout=0.25)
                       results.append('never here')
              except TimeoutError:
                  results.append('worker_timeout')

        async def worker_cancel(seconds):
              cond = Condition()
              taskid = kernel.add_task(worker(cond))
              results.append('sleep')
              await sleep(seconds)
              results.append('done')

        kernel.add_task(worker_cancel(1))
        kernel.run()
        self.assertEqual(results, [
                'sleep',
                'cond_wait',
                'worker_timeout',
                'done'
                ])

    def test_cond_notify_all(self):
        kernel = get_kernel()
        results = []
        async def worker(cond):
             async with cond:
                 results.append('cond_wait')
                 await cond.wait()
                 results.append('wait_done')

        async def worker_notify(seconds):
              cond = Condition()
              kernel.add_task(worker(cond))
              kernel.add_task(worker(cond))
              kernel.add_task(worker(cond))
              results.append('sleep')
              await sleep(seconds)
              async with cond:
                  results.append('notify')
                  cond.notify_all()
              results.append('done')

        kernel.add_task(worker_notify(1))
        kernel.run()
        self.assertEqual(results, [
                'sleep',
                'cond_wait',
                'cond_wait',
                'cond_wait',
                'notify',
                'done',
                'wait_done',
                'wait_done',
                'wait_done'
                ])

if __name__ == '__main__':
    unittest.main()