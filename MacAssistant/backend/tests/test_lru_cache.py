import unittest
import sys
import os

# Add the backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.llm_integration import LRUCache

class TestLRUCache(unittest.TestCase):

    def test_cache_initialization(self):
        cache = LRUCache(max_size=5)
        self.assertEqual(len(cache), 0)
        self.assertEqual(cache.max_size, 5)

    def test_put_and_get_within_size(self):
        cache = LRUCache(max_size=3)
        cache.put('a', 1)
        cache.put('b', 2)
        self.assertEqual(len(cache), 2)
        self.assertEqual(cache.get('a'), 1)
        self.assertEqual(cache.get('b'), 2)
        self.assertIsNone(cache.get('c'))

    def test_get_updates_recency(self):
        cache = LRUCache(max_size=3)
        cache.put('a', 1)
        cache.put('b', 2)
        cache.put('c', 3) # Cache: c (mru), b, a (lru)
        
        self.assertEqual(list(cache.cache.keys()), ['a', 'b', 'c'])

        cache.get('a') # Access 'a', making it MRU. Cache: a (mru), c, b (lru)
        self.assertEqual(list(cache.cache.keys()), ['b', 'c', 'a'])
        
        cache.get('b') # Access 'b', making it MRU. Cache: b (mru), a, c (lru)
        self.assertEqual(list(cache.cache.keys()), ['c', 'a', 'b'])


    def test_put_exceeds_max_size_evicts_lru(self):
        cache = LRUCache(max_size=2)
        cache.put('a', 1) # a
        cache.put('b', 2) # b, a
        self.assertEqual(len(cache), 2)
        self.assertIn('a', cache)
        self.assertIn('b', cache)

        cache.put('c', 3) # c, b (a should be evicted)
        self.assertEqual(len(cache), 2)
        self.assertNotIn('a', cache)
        self.assertIn('b', cache)
        self.assertIn('c', cache)
        self.assertEqual(list(cache.cache.keys()), ['b', 'c']) # b is lru, c is mru

        cache.put('d', 4) # d, c (b should be evicted)
        self.assertEqual(len(cache), 2)
        self.assertNotIn('b', cache)
        self.assertIn('c', cache)
        self.assertIn('d', cache)
        self.assertEqual(list(cache.cache.keys()), ['c', 'd'])

    def test_put_updates_existing_key_and_recency(self):
        cache = LRUCache(max_size=3)
        cache.put('a', 1)
        cache.put('b', 2)
        cache.put('c', 3) # c, b, a
        self.assertEqual(list(cache.cache.keys()), ['a', 'b', 'c'])
        
        cache.put('a', 10) # Update 'a', makes it MRU. Cache: a, c, b
        self.assertEqual(cache.get('a'), 10)
        self.assertEqual(len(cache), 3)
        self.assertEqual(list(cache.cache.keys()), ['b', 'c', 'a'])

    def test_contains(self):
        cache = LRUCache(max_size=2)
        cache.put('a', 1)
        self.assertTrue('a' in cache)
        self.assertFalse('b' in cache)

    def test_len(self):
        cache = LRUCache(max_size=5)
        self.assertEqual(len(cache), 0)
        cache.put('a', 1)
        self.assertEqual(len(cache), 1)
        cache.put('b', 2)
        self.assertEqual(len(cache), 2)
        cache.put('c', 3)
        cache.put('d', 4)
        cache.put('e', 5)
        self.assertEqual(len(cache), 5)
        cache.put('f', 6) # Evicts one
        self.assertEqual(len(cache), 5)

    def test_cache_with_zero_max_size(self):
        cache = LRUCache(max_size=0)
        cache.put('a', 1)
        self.assertIsNone(cache.get('a'))
        self.assertEqual(len(cache), 0)
        
    def test_cache_with_max_size_one(self):
        cache = LRUCache(max_size=1)
        cache.put('a',1)
        self.assertEqual(cache.get('a'), 1)
        cache.put('b',2) # evicts 'a'
        self.assertIsNone(cache.get('a'))
        self.assertEqual(cache.get('b'),2)
        self.assertEqual(len(cache),1)

if __name__ == '__main__':
    unittest.main()
