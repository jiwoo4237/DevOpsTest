variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone for the VM"
  type        = string
  default     = "us-central1-a"
}

variable "instance_name" {
  description = "GCE VM name"
  type        = string
  default     = "edu-k3s-vm"
}

variable "machine_type" {
  description = "GCE machine type"
  type        = string
  default     = "e2-medium"
}

variable "boot_disk_size_gb" {
  description = "Boot disk size in GB"
  type        = number
  default     = 30
}

variable "network_name" {
  description = "VPC network name"
  type        = string
  default     = "edu-k3s-vpc"
}

variable "subnetwork_name" {
  description = "Subnetwork name"
  type        = string
  default     = "edu-k3s-subnet"
}

variable "subnetwork_cidr" {
  description = "Subnetwork CIDR"
  type        = string
  default     = "10.40.0.0/24"
}

variable "ssh_user" {
  description = "SSH username for VM"
  type        = string
  default     = "ubuntu"
}

variable "ssh_public_key" {
  description = "Public SSH key content (without username prefix)"
  type        = string
}

variable "allow_http_cidrs" {
  description = "CIDR blocks allowed to access HTTP endpoints"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "labels" {
  description = "Labels for resources"
  type        = map(string)
  default     = {}
}