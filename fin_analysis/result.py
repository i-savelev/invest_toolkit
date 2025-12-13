class Res:
    def __init__(self, value, calc: str = '') -> None:
        self._value = value
        self._calc = calc

    def value(self):
        return self._value
    
    def calc(self):
        return self._calc