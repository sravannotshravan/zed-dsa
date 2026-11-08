// What LeetCode's Java env gives you: TreeNode, ListNode. LC holds helpers for prep.py's generated test harness.
import java.util.*;

class ListNode {
    int val; ListNode next;
    ListNode() {}
    ListNode(int val) { this.val = val; }
    ListNode(int val, ListNode next) { this.val = val; this.next = next; }
}

class TreeNode {
    int val; TreeNode left, right;
    TreeNode() {}
    TreeNode(int val) { this.val = val; }
    TreeNode(int val, TreeNode left, TreeNode right) { this.val = val; this.left = left; this.right = right; }
}

class LC {
    static ListNode list(int[] a) {
        ListNode head = null;
        for (int i = a.length - 1; i >= 0; i--) head = new ListNode(a[i], head);
        return head;
    }

    /** LeetCode level-order array -> TreeNode. */
    static TreeNode tree(Integer[] a) {
        if (a.length == 0 || a[0] == null) return null;
        TreeNode[] n = new TreeNode[a.length];
        for (int i = 0; i < a.length; i++) if (a[i] != null) n[i] = new TreeNode(a[i]);
        int k = 1;
        for (TreeNode x : n) {
            if (x == null) continue;
            if (k < n.length) x.left = n[k++];
            if (k < n.length) x.right = n[k++];
        }
        return n[0];
    }

    /** Any result -> JSON in LeetCode serialization. */
    static String j(Object x) {
        if (x == null) return "null";
        if (x instanceof String || x instanceof Character) return q(String.valueOf(x));
        if (x instanceof ListNode l) {
            List<Integer> out = new ArrayList<>();
            for (; l != null && out.size() < 100000; l = l.next) out.add(l.val);  // cycle guard
            return j(out);
        }
        if (x instanceof TreeNode t) {
            List<Integer> out = new ArrayList<>();
            List<TreeNode> level = new ArrayList<>(List.of(t));
            for (int i = 0; i < level.size(); i++) {
                TreeNode n = level.get(i);
                out.add(n == null ? null : n.val);
                if (n != null) { level.add(n.left); level.add(n.right); }
            }
            while (!out.isEmpty() && out.get(out.size() - 1) == null) out.remove(out.size() - 1);
            return j(out);
        }
        StringJoiner sj = new StringJoiner(",", "[", "]");
        if (x.getClass().isArray()) {
            for (int i = 0; i < java.lang.reflect.Array.getLength(x); i++) sj.add(j(java.lang.reflect.Array.get(x, i)));
            return sj.toString();
        }
        if (x instanceof Iterable<?> it) {
            for (Object o : it) sj.add(j(o));
            return sj.toString();
        }
        return String.valueOf(x);  // numbers, booleans
    }

    static String q(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            if (c == '"' || c == '\\') b.append('\\').append(c);
            else if (c < 32) b.append(String.format("\\u%04x", (int) c));
            else b.append(c);
        }
        return b.append('"').toString();
    }

    interface Test { Object go() throws Throwable; }

    /** One machine-readable line per test; anything else on stdout is the user's debug output. */
    static void run(int i, Test t) {
        long s = System.nanoTime();
        String r;
        try { r = j(t.go()); }
        catch (Throwable e) {
            StringBuilder b = new StringBuilder("!" + e);
            for (StackTraceElement f : e.getStackTrace()) if (f.getFileName() != null && f.getFileName().startsWith("Main")) b.append(" @line ").append(f.getLineNumber());
            r = b.toString().replace("\n", " ");
        }
        System.out.println("@@" + i + " " + (System.nanoTime() - s) / 1000000 + " " + r);
        System.out.flush();
    }
}
