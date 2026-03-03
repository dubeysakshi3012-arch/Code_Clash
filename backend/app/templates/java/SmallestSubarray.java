/**
 * Smallest Subarray with Sum >= K
 * 
 * Given an array of positive integers and integer K, return the length of 
 * the smallest contiguous subarray with sum >= K. If no such subarray exists, return 0.
 * 
 * Example:
 * Input: nums = [2, 1, 5, 2, 3, 2], K = 7
 * Output: 2
 * Explanation: The smallest subarray with sum >= 7 is [5, 2].
 */

import java.io.*;
import java.util.*;

public class SmallestSubarray {
    
    public static int smallestSubarraySum(int[] nums, int k) {
        /**
         * Find the length of the smallest contiguous subarray with sum >= k.
         * 
         * @param nums Array of positive integers
         * @param k Target sum threshold
         * @return Length of smallest subarray with sum >= k, or 0 if no such subarray exists
         */
        // TODO: Implement your solution here
        // Hint: Use sliding window technique
        int n = nums.length;
        int minLength = Integer.MAX_VALUE;
        int windowSum = 0;
        int left = 0;
        
        for (int right = 0; right < n; right++) {
            windowSum += nums[right];
            
            while (windowSum >= k) {
                minLength = Math.min(minLength, right - left + 1);
                windowSum -= nums[left];
                left++;
            }
        }
        
        return minLength == Integer.MAX_VALUE ? 0 : minLength;
    }
    
    // Fast I/O using BufferedReader
    public static void main(String[] args) throws IOException {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        
        // Read input
        String[] input = br.readLine().trim().split("\\s+");
        int[] nums = new int[input.length];
        for (int i = 0; i < input.length; i++) {
            nums[i] = Integer.parseInt(input[i]);
        }
        int k = Integer.parseInt(br.readLine().trim());
        
        // Calculate result
        int result = smallestSubarraySum(nums, k);
        
        // Output result
        System.out.println(result);
    }
}
