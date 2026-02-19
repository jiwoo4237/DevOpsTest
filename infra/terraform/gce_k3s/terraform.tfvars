project_id = "project-42e7f1f8-4a06-44aa-81d"
region     = "us-central1"
zone       = "us-central1-a"

instance_name      = "edu-k3s-vm"
machine_type       = "e2-medium"
boot_disk_size_gb  = 30
ssh_user           = "ubuntu"
ssh_public_key     = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINSux/K2ZvMl6AG+Wd9kZSBpdBLjeA7RBVYDhvXctyuU wldn39ew"

allow_http_cidrs = ["0.0.0.0/0"]

labels = {
  owner = "devops-class"
  stage = "training"
}