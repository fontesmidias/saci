def sum_numbers(a, b):
    """
    This function takes two numbers as input and returns their sum.

    Parameters:
    a (int or float): The first number to be summed.
    b (int or float): The second number to be summed.

    Returns:
    int or float: The sum of the two input numbers.
    """
    return a + b

# Example usage
if __name__ == "__main__":
    num1 = 5
    num2 = 7
    result = sum_numbers(num1, num2)
    print(f"The sum of {num1} and {num2} is {result}")