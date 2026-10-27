# 📋 Project To-Do List

This document tracks planned features, enhancements, and bug fixes for the **Anno Island Reskinner** application.

---

## 🎨 UI & User Experience
- [x] **Optimize Map & Dot Preview**
  * Improve rendering performance for large map files.
  * Fix alignment and scale scaling issues for prop markers (dots).
  * Add a legend/toggle to filter different object types in the preview window.

## 🛠️ Object & Prop Manipulation (rd3d)
- [ ] **Object Density Scaling (Increase/Decrease Objects)**
  * Implement an automated slider or percentage tool to scale down vegetation density (similar to custom script logic).
  * Ensure random distribution while thinning or multiplying props without breaking the fixed index sequence.

## ⛰️ Visuals & Environment
- [ ] **Find a Way to Change Mountain Textures**
  * Investigate mapping rules for internal island meshes.
  * Determine if cliff/mountain textures can be overridden cleanly via the `MaterialSetFileName` or if deep mesh patching is mandatory.
- [ ] **Lighting Settings Integration**
  * Add configuration options to adjust environment grids and lighting parameters.
  * Allow easy overriding of regional ambient values (`GlobalAmbientName`).

## 🐛 Bug Fixes & Stability
- [ ] **General Bug Squashing**
  * Resolve application freezes during large file compression/decompression.
  * Implement robust error handling for missing environment variables or unmapped tool paths in the Settings tab.
  * Fix validation parsing errors (e.g., boolean conversions like `0` to `false` in `IrrigationManager`).
