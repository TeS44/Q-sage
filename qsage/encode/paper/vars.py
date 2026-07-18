"""Variable id dispatcher (paper encoders)."""

class VarDispatcher:
    def __init__(self) -> None:
        self.next_var = 1

    def get_vars(self, n: int) -> list[int]:
        var_list = list(range(self.next_var, self.next_var + n))
        self.next_var = self.next_var + n
        return var_list

    def get_single_var(self) -> int:
        cur = self.next_var
        self.next_var += 1
        return cur

    def set_next_var(self, n: int) -> None:
        self.next_var = n
