package main

import (
	"math"
)

func calculateStandardDeviation(fileSizes map[string]int64) float64 {
	if len(fileSizes) == 0 {
		return 0.0
	}

	var sum int64
	for _, size := range fileSizes {
		sum += size
	}
	mean := float64(sum) / float64(len(fileSizes))

	var variance float64
	for _, size := range fileSizes {
		variance += math.Pow(float64(size)-mean, 2)
	}
	variance /= float64(len(fileSizes))

	return math.Sqrt(variance)
}

func calculateLargeByteThreshold(fileSizes map[string]int64) int64 {
	if len(fileSizes) == 0 {
		return 0
	}

	var sum int64
	for _, size := range fileSizes {
		sum += size
	}
	mean := float64(sum) / float64(len(fileSizes))

	var variance float64
	for _, size := range fileSizes {
		variance += math.Pow(float64(size)-mean, 2)
	}
	variance /= float64(len(fileSizes))
	stdDev := math.Sqrt(variance)

	return int64(mean + stdDev)
}
