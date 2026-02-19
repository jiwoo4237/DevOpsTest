locals {
  required_services = toset([
    "compute.googleapis.com",
  ])

  base_labels = {
    managed_by = "terraform"
    purpose    = "education"
    stack      = "gce-k3s"
  }

  merged_labels = merge(local.base_labels, var.labels)
}

resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "k3s_vpc" {
  name                    = var.network_name
  auto_create_subnetworks = false

  depends_on = [google_project_service.required]
}

resource "google_compute_subnetwork" "k3s_subnet" {
  name          = var.subnetwork_name
  region        = var.region
  network       = google_compute_network.k3s_vpc.id
  ip_cidr_range = var.subnetwork_cidr
}

resource "google_compute_firewall" "allow_ssh" {
  name    = "${var.instance_name}-allow-ssh"
  network = google_compute_network.k3s_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = [var.instance_name]
}

resource "google_compute_firewall" "allow_http_nodeport" {
  name    = "${var.instance_name}-allow-http"
  network = google_compute_network.k3s_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "30000-32767"]
  }

  source_ranges = var.allow_http_cidrs
  target_tags   = [var.instance_name]
}

resource "google_compute_address" "k3s_ip" {
  name   = "${var.instance_name}-ip"
  region = var.region
}

data "google_compute_image" "ubuntu" {
  family  = "ubuntu-2204-lts"
  project = "ubuntu-os-cloud"
}

resource "google_compute_instance" "k3s_vm" {
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = [var.instance_name]

  labels = local.merged_labels

  boot_disk {
    initialize_params {
      image = data.google_compute_image.ubuntu.self_link
      size  = var.boot_disk_size_gb
      type  = "pd-balanced"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.k3s_subnet.id
    access_config {
      nat_ip = google_compute_address.k3s_ip.address
    }
  }

  metadata = {
    ssh-keys = "${var.ssh_user}:${var.ssh_public_key}"
  }

  service_account {
    scopes = ["cloud-platform"]
  }

  depends_on = [
    google_compute_firewall.allow_ssh,
    google_compute_firewall.allow_http_nodeport,
  ]
}