# Geo Fence Upload

## Overview

**Scenario Name:** `geo_fence_upload`
**Description:** This scenario validates the capability to upload and retrieve a Geo-Fence (Area of Interest). It ensures that the system accepts valid GeoJSON definitions for geofencing and allows for their subsequent retrieval and verification.

## Execution Flow

The scenario executes the following sequence of steps:

### 1. Upload Geo Fence
- **Step:** `Upload Geo Fence`
- **Action:** Uploads a GeoJSON file defining the Area of Interest (AOI) to Flight Blender.
- **Context:** Sets up the spatial constraints for operations. The client stores the ID of the created geo-fence.

### 2. Verify Upload
- **Step:** `Get Geo Fence`
- **Action:** API call to retrieve the details of the uploaded geo-fence.
- **Verification:** Confirms that the geo-fence was successfully persisted and matches the uploaded definition.

### 3. Teardown
- **Step:** Cleanup
- **Action:** Automatically tears down the created geo-fence resources upon scenario completion.
- **Result:** Ensures the system returns to a clean state.
