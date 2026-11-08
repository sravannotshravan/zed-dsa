"""What LeetCode's Python env gives you for free. Solutions do `from lc import *`."""
from typing import *  # noqa: F401,F403  (List, Optional, ...)
from collections import *  # noqa: F401,F403  (deque, Counter, defaultdict, ...)
from heapq import *  # noqa: F401,F403
from bisect import *  # noqa: F401,F403
from itertools import *  # noqa: F401,F403
from functools import *  # noqa: F401,F403
from math import inf, gcd, lcm, comb, perm, sqrt, isqrt, ceil, floor, log2  # not *: math.pow would shadow pow(a, b, mod)
import math, random, re, string  # noqa: F401,E401


class ListNode:
    def __init__(self, val=0, next=None):
        self.val, self.next = val, next


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val, self.left, self.right = val, left, right


def build_list(a):
    head = None
    for v in reversed(a or []):
        head = ListNode(v, head)
    return head


def build_tree(a):
    """LeetCode level-order array -> TreeNode."""
    if not a or a[0] is None:
        return None
    nodes = [None if v is None else TreeNode(v) for v in a]
    kids = iter(nodes[1:])
    for n in nodes:
        if n:
            n.left, n.right = next(kids, None), next(kids, None)
    return nodes[0]


def to_plain(x):
    """Nodes/tuples -> plain JSON-ish values, LeetCode serialization."""
    if isinstance(x, ListNode):
        out = []
        while x and len(out) < 10**5:  # cycle guard
            out.append(x.val)
            x = x.next
        return out
    if isinstance(x, TreeNode):
        out, q = [], deque([x])
        while q:
            n = q.popleft()
            out.append(n and n.val)
            if n:
                q += [n.left, n.right]
        while out and out[-1] is None:
            out.pop()
        return out
    if isinstance(x, (list, tuple)):
        return [to_plain(i) for i in x]
    return x
