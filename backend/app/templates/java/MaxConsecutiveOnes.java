/**
 * Maximum Consecutive Ones
 * 
 * Given a binary array, find the maximum number of consecutive 1s.
 * 
 * Example:
 * Input: [1, 1, 0, 1, 1, 1]
 * Output: 3
 */

import java.io.*;
import java.util.*;

public class MaxConsecutiveOnes {
    
    public static int maxConsecutiveOnes(int[] nums) {
        /**
         * Find the maximum number of consecutive 1s in a binary array.
         * 
         * @param nums Binary array containing only 0s and 1s
         * @return Maximum number of consecutive 1s
         */
        // TODO: Implement your solution here
        int maxCount = 0;
        int currentCount = 0;
        
        for (int num : nums) {
            if (num == 1) {
                currentCount++;
                maxCount = Math.max(maxCount, currentCount);
            } else {
                currentCount = 0;
            }
        }
        
        return maxCount;
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
        
        // Calculate result
        int result = maxConsecutiveOnes(nums);
        
        // Output result
        System.out.println(result);
    }
}
