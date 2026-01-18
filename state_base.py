class State:
    name = "BASE"

    def enter(self, ctx):
        pass

    def update(self, ctx):
        """
        Возвращает:
        - None -> остаёмся в этом же состоянии
        - "STATE_NAME" -> переход в другое состояние
        """
        return None

    def exit(self, ctx):
        pass
