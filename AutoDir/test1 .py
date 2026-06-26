def max_sum_subarray(arr, k): 
    if len(arr)<k or k<=0:
        return None

    sum = 0
    for i in range(k):
        sum+=arr[i]

        max_sum = sum
	
    for i in range(k,len(arr)):
	    sum = sum+arr[i]-arr[i-k]
	    
    max_sum = sum
         
    return max_sum


arr= [2, 1, 5, 1, 3, 2], k=3 
# Output: 9