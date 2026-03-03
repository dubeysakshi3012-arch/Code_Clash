"""
Maximum Consecutive Ones

Given a binary array, find the maximum number of consecutive 1s.

Example:
Input: [1, 1, 0, 1, 1, 1]
Output: 3
"""

from typing import List


def max_consecutive_ones(nums: List[int]) -> int:
    """
    Find the maximum number of consecutive 1s in a binary array.
    
    Args:
        nums: Binary array containing only 0s and 1s
        
    Returns:
        Maximum number of consecutive 1s
    """
    # TODO: Implement your solution here
    max_count = 0
    current_count = 0
    
    for num in nums:
        if num == 1:
            current_count += 1
            max_count = max(max_count, current_count)
        else:
            current_count = 0
    
    return max_count


# Fast I/O for competitive programming
if __name__ == "__main__":
    import sys
    
    # Read input
    input_line = sys.stdin.readline().strip()
    nums = list(map(int, input_line.split()))
    
    # Calculate result
    result = max_consecutive_ones(nums)
    
    # Output result
    print(result)
