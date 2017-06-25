import random
import time


def weighted_truth(truth_percent):
    """ Return a boolean randomly, where weight of True is based on
    integer percentage distribution. """
    return truth_percent >= random.randint(1, 100)


def int_now():
    """Get the current time as UTC timestamp."""
    return int(time.time())
