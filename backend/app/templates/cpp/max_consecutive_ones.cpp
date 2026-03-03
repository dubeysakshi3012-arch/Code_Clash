/**
 * Maximum Consecutive Ones
 * 
 * Given a binary array, find the maximum number of consecutive 1s.
 * 
 * Example:
 * Input: [1, 1, 0, 1, 1, 1]
 * Output: 3
 */

#include <iostream>
#include <vector>
#include <algorithm>
#include <sstream>

using namespace std;

int maxConsecutiveOnes(vector<int>& nums) {
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
            maxCount = max(maxCount, currentCount);
        } else {
            currentCount = 0;
        }
    }
    
    return maxCount;
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
    
    // Calculate result
    int result = maxConsecutiveOnes(nums);
    
    // Output result
    cout << result << endl;
    
    return 0;
}
