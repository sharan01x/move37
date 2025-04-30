/**
 * Formats a date for display in the format: MM/DD/YYYY HH:MM AM/PM
 * 
 * @param date The date to format
 * @returns Formatted date string
 */
export function formatDateTimeForDisplay(date: Date): string {
  try {
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return 'Invalid date';
    }
    
    // Format as 24 Apr 2025
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const month = monthNames[date.getMonth()];
    const day = date.getDate();
    const year = date.getFullYear();
    
    // Format time as HH:MM in 24 hour format
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    
    return `${day} ${month} ${year} ${hours}:${minutes}`;
  } catch (error) {
    console.error('Error formatting date:', error);
    return 'Error formatting date';
  }
} 