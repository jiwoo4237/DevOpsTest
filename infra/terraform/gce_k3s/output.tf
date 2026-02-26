output "instance_name" {
  description = "GCE instance name"
  value       = google_compute_instance.k3s_vm.name
}

output "zone" {
  description = "GCE instance zone"
  value       = google_compute_instance.k3s_vm.zone
}

output "external_ip" {
  description = "Public IP of the VM"
  value       = google_compute_address.k3s_ip.address
}

output "ssh_command" {
  description = "SSH command for VM access"
  value       = "ssh ${var.ssh_user}@${google_compute_address.k3s_ip.address}"
}

output "ansible_inventory_line" {
  description = "Inventory line to use for ansible/inventory/gce_k3s.ini"
  value       = "${google_compute_address.k3s_ip.address} ansible_user=${var.ssh_user}"
}

output "service_url_hint" {
  description = "Expected app URL after deployment (ingress on 80/443)"
  value       = "https://${google_compute_address.k3s_ip.address}/ (fallback: http://${google_compute_address.k3s_ip.address}/)"
}