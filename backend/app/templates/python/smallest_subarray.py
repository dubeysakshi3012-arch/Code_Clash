"""
Smallest Subarray with Sum >= K

Given an array of positive integers and integer K, return the length of 
the smallest contiguous subarray with sum >= K. If no such subarray exists, return 0.

Example:
Input: nums = [2, 1, 5, 2, 3, 2], K = 7
Output: 2
Explanation: The smallest subarray with sum >= 7 is [5, 2].
"""

from typing import List


def smallest_subarray_sum(nums: List[int], k: int) -> int:
    """
    Find the length of the smallest contiguous subarray with sum >= k.
    
    Args:
        nums: Array of positive integers
        k: Target sum threshold
        
    Returns:
        Length of smallest subarray with sum >= k, or 0 if no such subarray exists
    """
    # TODO: Implement your solution here
    # Hint: Use sliding window technique
    n = len(nums)
    min_length = float('inf')
    window_sum = 0
    left = 0
    
    for right in range(n):
        window_sum += nums[right]
        
        while window_sum >= k:
            min_length = min(min_length, right - left + 1)
            window_sum -= nums[left]
            left += 1
    
    return min_length if min_length != float('inf') else 0


# Fast I/O for competitive programming
if __name__ == "__main__":
    import sys
    
    # Read input
    input_line = sys.stdin.readline().strip()
    nums = list(map(int, input_line.split()))
    k = int(sys.stdin.readline().strip())
    
    # Calculate result
    result = smallest_subarray_sum(nums, k)
    
    # Output result
    print(result)
