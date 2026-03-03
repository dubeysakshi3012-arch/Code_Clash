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

#include <iostream>
#include <vector>
#include <algorithm>
#include <climits>
#include <sstream>

using namespace std;

int smallestSubarraySum(vector<int>& nums, int k) {
    /**
     * Find the length of the smallest contiguous subarray with sum >= k.
     * 
     * @param nums Array of positive integers
     * @param k Target sum threshold
     * @return Length of smallest subarray with sum >= k, or 0 if no such subarray exists
     */
    // TODO: Implement your solution here
    // Hint: Use sliding window technique
    int n = nums.size();
    int minLength = INT_MAX;
    int windowSum = 0;
    int left = 0;
    
    for (int right = 0; right < n; right++) {
        windowSum += nums[right];
        
        while (windowSum >= k) {
            minLength = min(minLength, right - left + 1);
            windowSum -= nums[left];
            left++;
        }
    }
    
    return minLength == INT_MAX ? 0 : minLength;
}

// Fast I/O for competitive programming
int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    
    // Read input
    string line;
    getline(cin, line);
    stringstream ss(line);
    vector<int> nums;
    int num;
    while (ss >> num) {
        nums.push_back(num);
    }
    int k;
    cin >> k;
    
    // Calculate result
    int result = smallestSubarraySum(nums, k);
    
    // Output result
    cout << result << endl;
    
    return 0;
}
